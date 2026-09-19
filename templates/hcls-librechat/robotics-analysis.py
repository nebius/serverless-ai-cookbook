"""Measure saved native video and LeRobot outputs without any inference.

Read the published result/manifest contracts, never guess *.mp4 siblings.
Numeric integrity and decoded differences are not physical-action validation.
"""
import argparse
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile
import tempfile

import numpy as np
import pyarrow.parquet as pq

from scientific_receipts import file_measurement, verify_file


def identity(path):
    size, digest = file_measurement(path)
    return {'size_bytes': size, 'sha256': digest}


def unpack_bundle(path, destination):
    """Extract the explicit tar/zstd transport, preserving every regular file."""
    destination.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='robotics-tar-') as temporary:
        raw = Path(temporary) / 'bundle.tar'
        with path.open('rb') as stream:
            compressed = stream.read(4) == b'\x28\xb5\x2f\xfd'
        if compressed:
            with raw.open('wb') as output:
                subprocess.run(['zstd', '-d', '-c', str(path)], stdout=output, check=True)
        else:
            raw = path
        with tarfile.open(raw, mode='r:') as archive:
            seen = set()
            for member in archive:
                name = PurePosixPath(member.name)
                if name.is_absolute() or '..' in name.parts or not (member.isdir() or member.isfile()):
                    raise ValueError('Dataset archive must contain relative regular files/directories.')
                if name in seen:
                    raise ValueError('Dataset archive contains duplicate paths.')
                seen.add(name)
                target = destination / str(name)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with archive.extractfile(member) as source, target.open('xb') as output:
                        shutil.copyfileobj(source, output)
    candidates = list(destination.glob('**/meta/info.json'))
    if len(candidates) != 1:
        raise ValueError('Expected exactly one LeRobot dataset root.')
    return candidates[0].parent.parent


def probe(path):
    value = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
        '-show_entries', 'stream=width,height,nb_read_frames,avg_frame_rate,duration,codec_name',
        '-of', 'json', str(path)], text=True))
    if len(value.get('streams', [])) != 1:
        raise ValueError('Expected one readable video stream.')
    stream = value['streams'][0]
    return {**stream, 'nb_read_frames': int(stream['nb_read_frames']), **identity(path)}


def frames(path, width, height):
    process = subprocess.Popen(['ffmpeg', '-v', 'error', '-i', str(path), '-f', 'rawvideo',
                                '-pix_fmt', 'rgb24', 'pipe:1'], stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL)
    count = width * height * 3
    try:
        while True:
            raw = process.stdout.read(count)
            if not raw:
                break
            if len(raw) != count:
                raise ValueError('Incomplete decoded video frame.')
            yield np.frombuffer(raw, dtype=np.uint8).reshape(height, width, 3)
        if process.wait() != 0:
            raise ValueError('Video decode failed.')
    finally:
        process.stdout.close()
        if process.poll() is None:
            process.terminate()
            process.wait()


def compare_video(source, generated):
    before, after = probe(source), probe(generated)
    metadata_equal = all(before[k] == after[k] for k in
                         ('width', 'height', 'nb_read_frames', 'avg_frame_rate'))
    result = {'source': before, 'output': after, 'metadata_equal': metadata_equal,
              'bytes_equal': before['sha256'] == after['sha256'],
              'geometry_preservation_verified': False, 'physical_action_alignment_verified': False}
    if not metadata_equal:
        result['decoded_comparison'] = 'not_aligned_metadata_differs'
        return result
    changed = count = 0
    absolute = temporal_before = temporal_after = 0.
    source_rgb, output_rgb = np.zeros(3), np.zeros(3)
    previous = None
    left = frames(source, before['width'], before['height'])
    right = frames(generated, after['width'], after['height'])
    try:
        for a, b in zip(left, right, strict=True):
            difference = np.abs(a.astype(np.int16) - b.astype(np.int16))
            changed += int(np.any(difference))
            absolute += float(difference.mean())
            source_rgb += a.mean(axis=(0, 1)); output_rgb += b.mean(axis=(0, 1))
            if previous is not None:
                temporal_before += float(np.abs(a.astype(np.int16)-previous[0]).mean())
                temporal_after += float(np.abs(b.astype(np.int16)-previous[1]).mean())
            previous = (a.astype(np.int16), b.astype(np.int16))
            count += 1
    finally:
        left.close(); right.close()
    if count != before['nb_read_frames'] or not count:
        raise ValueError('Decoded count differs from readable video metadata.')
    result.update(decoded_frames=count, changed_frames=changed, pixel_mae=absolute/count,
                  source_mean_rgb=(source_rgb/count).tolist(), output_mean_rgb=(output_rgb/count).tolist(),
                  source_adjacent_frame_mae=temporal_before/(count-1) if count>1 else None,
                  output_adjacent_frame_mae=temporal_after/(count-1) if count>1 else None)
    return result


def dataset_values(root):
    files = sorted((root / 'data').glob('**/*.parquet'))
    if not files:
        raise ValueError('LeRobot dataset contains no recorded Parquet rows.')
    import pyarrow as pa
    table = pa.concat_tables([pq.read_table(path) for path in files])
    if not table.num_rows or len(set(table.column_names)) != len(table.column_names):
        raise ValueError('LeRobot recorded rows/field names are empty or ambiguous.')
    return table


def compare_dataset(source, output, selected_cameras):
    a, b = dataset_values(source), dataset_values(output)
    fields = []
    schema_equal = a.schema.equals(b.schema, check_metadata=False)
    for field in a.schema:
        left = a[field.name]
        present = field.name in b.column_names
        equal = present and left.equals(b[field.name])
        # Stable Arrow IPC bytes also retain exact floating representations.
        bits_equal = False
        if present and left.type == b[field.name].type:
            import pyarrow as pa
            def column_bytes(column):
                sink = pa.BufferOutputStream()
                with pa.ipc.new_stream(sink, pa.schema([field])) as writer:
                    writer.write_table(pa.table([column.combine_chunks()], schema=pa.schema([field])))
                return sink.getvalue().to_pybytes()
            bits_equal = column_bytes(left) == column_bytes(b[field.name])
        values = np.asarray(left.to_pylist())
        fields.append({'field': field.name, 'arrow_type': str(field.type),
                       'shape': list(values.shape), 'scalar_values': int(values.size),
                       'values_equal': bool(equal), 'arrow_bytes_equal': bits_equal})
    source_info = json.loads((source/'meta/info.json').read_bytes())
    result_info = json.loads((output/'meta/info.json').read_bytes())
    cameras = sorted(key for key, value in source_info['features'].items() if value.get('dtype') == 'video')
    if not selected_cameras or not set(selected_cameras) <= set(cameras):
        raise ValueError('Select actual source camera names explicitly.')
    def episodes(root):
        rows = [r for p in sorted((root/'meta/episodes').glob('**/*.parquet')) for r in pq.read_table(p).to_pylist()]
        return [{k: v for k, v in row.items() if not k.startswith('stats/')} for row in rows]
    episode_before, episode_after = episodes(source), episodes(output)
    def semantic_episode(row):
        # Physical shard locations may change while recorded identities and
        # timestamps stay exact. Preserve both locators in the evidence below.
        return {k:v for k,v in row.items() if not k.endswith(('/chunk_index','/file_index'))}
    episode_equal = bool(episode_before) and [semantic_episode(r) for r in episode_before] == [semantic_episode(r) for r in episode_after]
    if len(episode_before) != len(episode_after):
        raise ValueError('Episode population differs; no implicit media pairing.')
    def video_path(root, info, episode, camera):
        value = info['video_path'].format(video_key=camera,
            chunk_index=int(episode[f'videos/{camera}/chunk_index']),
            file_index=int(episode[f'videos/{camera}/file_index']))
        target = (root/value).resolve()
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            raise ValueError('Episode video locator does not identify a file in its dataset.')
        return target
    media = []
    for camera in cameras:
        pairs = {}
        for original_episode, returned_episode in zip(episode_before,episode_after,strict=True):
            if original_episode['episode_index'] != returned_episode['episode_index']:
                raise ValueError('Episode identities differ; no implicit media pairing.')
            left=video_path(source,source_info,original_episode,camera)
            right=video_path(output,result_info,returned_episode,camera)
            pair=(left,right)
            pairs.setdefault(pair,[]).append(original_episode['episode_index'])
        for (left,right),ids in pairs.items():
            row = compare_video(left,right)
            media.append({'camera':camera,'file':str(right.relative_to(output)),
                          'source_file':str(left.relative_to(source)), 'episode_ids':ids,
                          'selected':camera in selected_cameras,**row})
    nonvideo_equal = schema_equal and a.num_rows == b.num_rows and all(
        x['values_equal'] and x['arrow_bytes_equal'] for x in fields)
    unselected_equal = all(row['bytes_equal'] and row.get('changed_frames') == 0
                          for row in media if not row['selected'])
    return {'source_rows': a.num_rows, 'output_rows': b.num_rows, 'schema_equal': schema_equal,
            'nonvideo_fields': fields, 'scalar_values': sum(row['scalar_values'] for row in fields),
            'all_nonvideo_values_and_types_exact': nonvideo_equal,
            'episode_identities_and_timestamps_equal': episode_equal,
            'source_episodes': episode_before, 'output_episodes': episode_after,
            'fps_equal': source_info['fps'] == result_info['fps'],
            'all_unselected_media_bytes_and_pixels_equal': unselected_equal, 'media': media}


def analyze(plan, output):
    output.mkdir(parents=True, exist_ok=True)
    native_path, manifest_path = Path(plan['native_result']), Path(plan['manifest_file'])
    native = json.loads(native_path.read_bytes())
    if native.get('schema') != 'scientific-native-file/v1' or native.get('content_type') != 'video/mp4':
        raise ValueError('Expected the verified native-file/v1 MP4 result, not a guessed sibling.')
    movie = Path(native['file']['path'])
    if movie.parent.resolve() != native_path.parent.resolve():
        raise ValueError('Native video must belong to the same saved operation.')
    verify_file(movie, native['file'])
    manifest = json.loads(manifest_path.read_bytes())
    if manifest.get('schema') != 'fs2-serve.nebius.ai/scientific-artifact-manifest/v1':
        raise ValueError('Expected the published scientific artifact manifest.')
    variants = []
    for i, entry in enumerate(manifest['entries']):
        artifact_path = manifest_path.parent / f'output-{i:02d}.artifact'
        verify_file(artifact_path, entry['artifact'])
        if entry['semantic_type'] == 'lerobot-v3-augmented-bundle/v1':
            variants.append((entry, artifact_path))
    index = plan.get('variant_index', 0)
    if type(index) is not int or not 0 <= index < len(variants):
        raise ValueError('Requested dataset variant is absent from the manifest.')
    entry, archive = variants[index]
    if entry['artifact']['media_type'] != 'application/x-tar' or entry['artifact']['compression'] != 'zstd':
        raise ValueError('This dataset comparison expects the published tar/zstd bundle contract.')
    original_video, original_archive = Path(plan['source_video']), Path(plan['source_archive'])
    with tempfile.TemporaryDirectory(prefix='robotics-analysis-') as temporary:
        source = unpack_bundle(original_archive, Path(temporary)/'source')
        generated = unpack_bundle(archive, Path(temporary)/'output')
        dataset = compare_dataset(source, generated, plan['selected_cameras'])
        video = compare_video(original_video, movie)
    shutil.copyfile(movie, output/'native-output.mp4')
    shutil.copyfile(archive, output/'augmented-dataset.tar.zst')
    limits = [
        'Decoded RGB differences and adjacent-frame changes are measurements, not geometry or motion-preservation proofs.',
        'Matching actions/states/timestamps does not prove visual-action alignment, physical validity or policy-training suitability.',
        'Review original and returned clips at matching frames for geometry, contacts, flicker and temporal artifacts.',
        'RGB channel means are not luminance; nonzero frame differences do not prove correct recorded motion.',
    ]
    result = {'schema': 'scientific-robotics-comparison/v1', 'native_video': video, 'dataset': dataset,
              'variant_index': index, 'variant_count': len(variants), 'artifact_name': entry['name'],
              'sources': {name: {'path': plan[name], **identity(Path(plan[name]))} for name in
                          ('source_video','source_archive','native_result','manifest_file')},
              'geometry_preservation_verified': False, 'physical_action_alignment_verified': False,
              'limitations': limits}
    (output/'metrics.json').write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    lines = ['# Recorded augmentation measurements', '',
             f"Native clip: {video['source']['nb_read_frames']} → {video['output']['nb_read_frames']} frames; metadata equal: {video['metadata_equal']}.",
             f"Dataset: {dataset['source_rows']} → {dataset['output_rows']} rows; {dataset['scalar_values']} nonvideo scalar values.",
             f"All nonvideo values/types exact: {dataset['all_nonvideo_values_and_types_exact']}.",
             f"Episode identities/timestamps equal: {dataset['episode_identities_and_timestamps_equal']}.",
             f"Unselected media bytes/pixels exact: {dataset['all_unselected_media_bytes_and_pixels_equal']}.", '',
             '| Camera | Shard | Selected | Frames | Changed frames | Pixel MAE |',
             '|---|---|---|---:|---:|---:|']
    for row in dataset['media']:
        lines.append(f"| {row['camera']} | {row['file']} | {row['selected']} | {row['output']['nb_read_frames']} | {row.get('changed_frames','not aligned')} | {row.get('pixel_mae','not aligned')} |")
    lines += ['', '## Interpretation limits', '', *['- '+item for item in limits], '',
              'Exact inputs, every measured field, returned files and hashes are retained in metrics.json. No new inference was submitted.']
    (output/'report.md').write_text('\n'.join(lines)+'\n')
    files = {p.name: identity(p) for p in sorted(output.iterdir()) if p.is_file()}
    (output/'completion-manifest.json').write_text(json.dumps({'files': files, 'model_calls': 0}, indent=2)+'\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    analyze(json.loads(args.plan.read_bytes()), args.output_dir)


if __name__ == '__main__':
    main()
