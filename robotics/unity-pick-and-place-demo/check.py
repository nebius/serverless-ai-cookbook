"""Validate downloaded Unity results with Python's standard library and FFmpeg."""
import argparse
import csv
import json
import math
from pathlib import Path
import struct
import sqlite3
import statistics
import subprocess
import zlib

def validate_png(path):
    # Decode the chunk stream using stdlib, so downloaded results need no image library.
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"invalid PNG: {path}")
    offset, compressed, header, ended = 8, bytearray(), None, False
    while offset < len(data):
        length = struct.unpack(">I", data[offset:offset + 4])[0]
        kind = data[offset + 4:offset + 8]
        payload = data[offset + 8:offset + 8 + length]
        crc = struct.unpack(">I", data[offset + 8 + length:offset + 12 + length])[0]
        if zlib.crc32(kind + payload) != crc:
            raise ValueError(f"PNG checksum mismatch: {path}")
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", payload)
        elif kind == b"IDAT":
            compressed.extend(payload)
        elif kind == b"IEND":
            ended = True
            break
        offset += length + 12
    if not header or not ended:
        raise ValueError("incomplete PNG")
    width, height, depth, color, compression, filtering, interlace = header
    channels = {0: 1, 2: 3, 6: 4}.get(color)
    if not width or not height or depth != 8 or not channels or (compression, filtering, interlace) != (0, 0, 0):
        raise ValueError("expected a non-interlaced 8-bit camera PNG")
    if len(zlib.decompress(compressed)) != height * (1 + width * channels):
        raise ValueError("incomplete PNG pixels")


def measurements(root, require_motion=True):
    with (Path(root) / "joints.csv").open() as stream:
        reader = csv.DictReader(stream)
        expected = ["time_s"] + [f"joint_{i}_deg" for i in range(6)] + ["grip"]
        if reader.fieldnames != expected:
            raise ValueError("unexpected joint CSV header")
        rows = [[float(row[key]) for key in expected] for row in reader]
    if len(rows) < 2 or any(not math.isfinite(value) for row in rows for value in row):
        raise ValueError("invalid joint samples")
    if rows[0][0] < 0 or any(b[0] <= a[0] for a, b in zip(rows, rows[1:])):
        raise ValueError("sample times must increase")
    if any(not -0.05 <= row[-1] <= 1.05 for row in rows):
        raise ValueError("grip outside physical tolerance around 0 to 1")
    motion = max(max(row[i] for row in rows) - min(row[i] for row in rows) for i in range(1, 7))
    if require_motion and motion < 1:
        raise ValueError("no measured joint motion of at least one degree")
    return {"duration_seconds": rows[-1][0] - rows[0][0],
            "joint_samples": len(rows), "max_joint_range_deg": motion,
            "grip_range": max(row[-1] for row in rows) - min(row[-1] for row in rows)}


def numeric_csv(path, fields):
    with path.open() as stream:
        reader=csv.DictReader(stream)
        if not set(fields)<=set(reader.fieldnames or []): raise ValueError(f'Missing CSV fields: {path.name}')
        rows=list(reader)
    for row in rows:
        for key in fields: row[key]=float(row[key])
        if any(not math.isfinite(row[key]) for key in fields): raise ValueError(f'Nonfinite CSV value: {path.name}')
    if rows and (rows[0]['time_s']<0 or any(b['time_s']<=a['time_s'] for a,b in zip(rows,rows[1:]))):
        raise ValueError(f'CSV sample times must increase: {path.name}')
    return rows


def task_measurements(root):
    root=Path(root)
    renderer=None
    if (root/'renderer.json').exists():
        renderer=json.loads((root/'renderer.json').read_text())
        if 'NVIDIA' not in renderer['vendor']:
            raise ValueError('Expected native NVIDIA camera rendering')
    task=json.loads((root/'task.json').read_text())
    metadata=json.loads((root/'policy-metadata.json').read_text())
    traces=[json.loads(line) for line in (root/'policy.jsonl').read_text().splitlines()]
    vision=[json.loads(line) for line in (root/'perception.jsonl').read_text().splitlines()]
    objects=numeric_csv(root/'objects.csv',['time_s','x_m','y_m','z_m','grip','left_contact','right_contact'])
    applied=numeric_csv(root/'applied.csv',['time_s','observation_stamp']+[f'v{i}' for i in range(6)])
    if any(not -.05<=row['grip']<=1.05 or row['left_contact'] not in (0,1) or row['right_contact'] not in (0,1) for row in objects):
        raise ValueError('Invalid object grip or contact value')
    if not task.get('success') or task.get('phase')!='done': raise ValueError('Physical pick-and-place incomplete')
    if len(objects)<10 or len(traces)<10 or len(vision)<2 or len(applied)<10: raise ValueError('Missing task evidence')
    points=[[row[k] for k in ['x_m','y_m','z_m']] for row in objects]
    lift=max(p[2] for p in points)
    displacement=max(math.dist(points[0],p) for p in points)
    placed=math.dist(points[-1],[-.20,.25,.05])
    contact=any(row['left_contact']==1 and row['right_contact']==1 and p[2]>.15 for row,p in zip(objects,points))
    if lift<.15 or displacement<.4 or placed>.04 or not contact or float(objects[-1]['grip'])>.1:
        raise ValueError('Cube was not physically grasped, carried and released into the tray')
    phases={t['phase'] for t in traces}
    if not {'approach','descend','grasp','lift','carry','lower','release','retreat','done'}<=phases:
        raise ValueError('Incomplete task sequence')
    by_stamp={round(t['stamp'][0]+t['stamp'][1]*1e-9,4):t for t in traces}
    for t in traces:
        for key in ['q','observation','action']:
            if len(t[key])!=6 or any(not math.isfinite(v) for v in t[key]): raise ValueError('Invalid controller trace')
        if max(map(abs,t['action']))>metadata['velocity_limit']+1e-6: raise ValueError('Unbounded controller action')
    for row in applied:
        t=by_stamp.get(round(float(row['observation_stamp']),4))
        if t is None or any(abs(float(row[f'v{i}'])-t['action'][i])>1e-6 for i in range(6)):
            raise ValueError('Applied command does not match learned controller')
    first=next((v for v in vision if v['phase'] in ['locate','approach']),None)
    if first is None or first['red_pixels']<20 or math.dist(first['cube_estimate'],points[0])>.015:
        raise ValueError('Camera localization did not match the pickup cube')
    counts={}
    dbs=list((root/'rosbag').glob('*.db3'))
    if not dbs or not (root/'rosbag/metadata.yaml').is_file(): raise ValueError('Missing ROS recording')
    for db in dbs:
        with sqlite3.connect(f'file:{db}?mode=ro',uri=True) as connection:
            for topic,count in connection.execute('SELECT topics.name,count(*) FROM messages JOIN topics ON messages.topic_id=topics.id GROUP BY topics.name'):
                counts[topic]=counts.get(topic,0)+count
    if any(counts.get(t,0)<10 for t in ['/joint_states','/tool_pose','/joint_commands','/camera/image/compressed','/gripper_command','/gripper_contacts','/cube_ground_truth','/task_phase']):
        raise ValueError('Empty task ROS recording')
    return {**({'renderer':renderer} if renderer else {}),'model_sha256':metadata['sha256'],'policy_observations':len(traces),'applied_commands':len(applied),
        'ros_message_counts':counts,'cube_lift_height_m':lift,'cube_displacement_m':displacement,
        'placement_error_m':placed,'camera_localization_error_m':math.dist(first['cube_estimate'],points[0]),
        'inference_latency_p50_ms':statistics.median(t['latency_ms'] for t in traces)}


def frame_timing(root):
    root=Path(root)
    simulation=json.loads((root/'simulation.json').read_text())
    count=simulation['frames']
    fps=simulation['capture_fps']
    with (root/'frames.csv').open() as stream:
        rows=list(csv.DictReader(stream))
    times=[float(row['time_s']) for row in rows]
    duration=float(simulation['duration_seconds'])
    if fps!=15 or len(times)!=count or [int(row['frame']) for row in rows]!=list(range(count)):
        raise ValueError('Invalid camera timing or frame sequence')
    if not times or any(not math.isfinite(t) for t in times) or times[0]<0 or times[-1]>duration:
        raise ValueError('Invalid camera timestamps')
    if any(b<=a for a,b in zip(times,times[1:])) or duration-times[0]<duration*.95:
        raise ValueError('Incomplete camera timeline')
    if count/duration<fps*.85 or max(b-a for a,b in zip(times,times[1:]))>.5:
        raise ValueError('Camera capture too slow for a smooth 15 FPS video')
    return times,duration,fps


def check(root, result=None):
    root = Path(root)
    if result is None: result = json.loads((root / "result.json").read_text())
    if result.get("success") is not True:
        raise ValueError(f"run failed: {result.get('error', 'see logs')}")
    requested = float(result["requested_seconds"])
    if not math.isfinite(requested) or not 5 <= requested <= 600:
        raise ValueError("invalid requested duration")
    if result.get("task") != "pick_place":
        raise ValueError("expected a pick-and-place result")
    actual = measurements(root)
    if not (root/'renderer.json').is_file():
        raise ValueError("Missing renderer receipt")
    for key, value in task_measurements(root).items():
        if value != result[key]:
            raise ValueError(f"task summary disagrees with artifacts: {key}")
    for key, value in actual.items():
        if not math.isclose(value, result[key]):
            raise ValueError(f"summary disagrees with CSV: {key}")
    simulation = json.loads((root / "simulation.json").read_text())
    frames = sorted((root / "images").glob("frame_*.png"))
    if len(frames) < 2 or len(frames) != result["image_count"] or len(frames) != simulation["frames"]:
        raise ValueError("missing camera images")
    if not 5 <= simulation["duration_seconds"] <= requested + 30:
        raise ValueError("invalid simulation completion receipt")
    for frame in frames:
        validate_png(frame)
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
        "-show_entries", "stream=width,height:format=duration", "-of", "json", str(root / "preview.mp4")],
        check=True, capture_output=True, text=True)
    video = json.loads(probe.stdout)
    times,duration,fps=frame_timing(root)
    if not video["streams"] or abs(float(video["format"]["duration"])-(duration-times[0]))>1/fps+.1:
        raise ValueError("empty or truncated preview video")
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(root / "preview.mp4"),
                    "-f", "null", "-"], check=True, capture_output=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    print(json.dumps(check(parser.parse_args().directory), indent=2))
