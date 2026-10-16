"""Small artifact and process checks; fixtures are not Unity validation."""
import csv
import json
import os
from pathlib import Path
import struct
import shutil
import subprocess
import sys
import tempfile
import time
import zlib
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from check import check
from prepare import prepare
from runtime.run import run
from test_task import task_fixtures


def fixtures(root):
    root = Path(root)
    (root / 'images').mkdir()
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data))
    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 2, 2, 8, 2, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(b'\x00' + b'\xff\x00\x00' * 2 + b'\x00' + b'\x00\xff\x00' * 2))
           + chunk(b'IEND', b''))
    for i in range(75):
        (root / f'images/frame_{i:05d}.png').write_bytes(png)
    with (root / 'joints.csv').open('w') as stream:
        writer = csv.writer(stream)
        writer.writerow(['time_s'] + [f'joint_{i}_deg' for i in range(6)] + ['grip'])
        for i in range(6):
            writer.writerow([i, i * 2, 0, 0, 0, 0, 0, i / 5])
    (root/'simulation.json').write_text(json.dumps({'duration_seconds':5,'frames':75,'capture_fps':15}))
    (root/'frames.csv').write_text('frame,time_s\n'+''.join(f'{i},{i/15+(i%5)*.001}\n' for i in range(75)))
    task_fixtures(root)


def rejected(action):
    try:
        action()
    except (ValueError, OSError, subprocess.CalledProcessError, struct.error, zlib.error):
        return
    raise AssertionError('invalid input accepted')


def main():
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        output = base / 'ok'
        with patch('shutil.copystat', side_effect=PermissionError('Object Storage has no POSIX metadata')):
            assert run(output, 5, [sys.executable, __file__, '--fake']) == 0
        assert check(output)['max_joint_range_deg'] == 10
        copied=[];real_copy=shutil.copyfile
        def upload(source,destination):
            if Path(source).suffix=='.png':
                assert not (Path(destination).parents[1]/'result.json').exists()
                raise OSError('simulated image upload failure')
            copied.append(Path(source).name)
            return real_copy(source,destination)
        interrupted=base/'interrupted'
        with patch('runtime.run.shutil.copyfile',side_effect=upload):
            assert run(interrupted,5,[sys.executable,__file__,'--fake'])==1
        receipt=json.loads((interrupted/'result.json').read_text())
        assert receipt['success'] is False and 'simulated image upload failure' in receipt['error']
        assert 'result.json' not in copied
        failed_upload=base/'failed-upload'
        with patch('runtime.run.shutil.copyfile',side_effect=OSError('simulated log upload failure')):
            assert run(failed_upload,5,[sys.executable,'-c','raise SystemExit(7)'])==7
        receipt=json.loads((failed_upload/'result.json').read_text())
        assert receipt['success'] is False and 'exit status 7' in receipt['error'] and 'log upload failure' in receipt['error']

        verify=base/'verification-failed'
        def destination_check(root,result=None):
            if Path(root)==verify: raise ValueError('simulated destination verification failure')
            return check(root,result=result)
        with patch('runtime.run.check',side_effect=destination_check):
            assert run(verify,5,[sys.executable,__file__,'--fake'])==1
        receipt=json.loads((verify/'result.json').read_text())
        assert receipt['success'] is False and 'destination verification failure' in receipt['error']
        unwritable=base/'receipt-unwritable';real_write=Path.write_text
        def receipt_write(path,*args,**kwargs):
            if path==unwritable/'result.json': raise PermissionError('simulated receipt write failure')
            return real_write(path,*args,**kwargs)
        with patch.object(Path,'write_text',receipt_write):
            assert run(unwritable,5,[sys.executable,__file__,'--fake'])==1
        assert not (unwritable/'result.json').exists()

        timing=(output/'frames.csv').read_text()
        (output/'frames.csv').write_text(timing.replace('0,0.0','0,nan'))
        rejected(lambda: check(output))
        (output/'frames.csv').write_text(timing)
        (output/'frames.csv').unlink()
        rejected(lambda: check(output))
        (output/'frames.csv').write_text(timing)
        receipt=json.loads((output/'result.json').read_text())
        rejected(lambda: check(output,result={**receipt,'task':'reaching'}))
        simulation=json.loads((output/'simulation.json').read_text())
        (output/'simulation.json').write_text(json.dumps({k:v for k,v in simulation.items() if k!='capture_fps'}))
        try:check(output)
        except KeyError:pass
        else:raise AssertionError('Accepted legacy camera timing')
        (output/'simulation.json').write_text(json.dumps(simulation))
        rejected(lambda: run(output, 5))
        rejected(lambda: prepare(output))
        rejected(lambda: run(base / 'nan', float('nan')))
        assert not (base / 'nan').exists()
        frame = output / 'images/frame_00000.png'
        image = frame.read_bytes()
        frame.unlink()
        rejected(lambda: check(output))
        frame.write_bytes(image)
        image = frame.read_bytes()
        frame.write_bytes(b'broken')
        rejected(lambda: check(output))
        frame.write_bytes(image)
        rows = (output / 'joints.csv').read_text()
        with (output / 'joints.csv').open('w') as stream:
            writer = csv.writer(stream)
            writer.writerow(['time_s'] + [f'joint_{i}_deg' for i in range(6)] + ['grip'])
            for i in range(6): writer.writerow([i, 0, 0, 0, 0, 0, 0, i / 5])
        rejected(lambda: check(output))
        (output / 'joints.csv').write_text(rows.replace('2,4', 'nan,4'))
        rejected(lambda: check(output))
        (output / 'joints.csv').write_text(rows)
        video = output / 'preview.mp4'
        encoded = video.read_bytes()
        video.write_bytes(b'broken video')
        rejected(lambda: check(output))
        video.write_bytes(encoded)
        video.unlink()
        rejected(lambda: check(output))
        failed = base / 'failed'
        assert run(failed, 5, [sys.executable, '-c', 'raise SystemExit(7)']) == 7
        assert json.loads((failed / 'result.json').read_text())['success'] is False
        assert run(base / 'missing', 5, ['/no/such/unity']) == 1
        from itertools import count
        with patch('runtime.run.time.monotonic', side_effect=count(0,20)):
            assert run(base / 'timeout', 5, [sys.executable, '-c', 'import time; time.sleep(60)']) == 1
        assert 'timed out' in json.loads((base / 'timeout/result.json').read_text())['error']
        readonly = base / 'readonly'
        readonly.mkdir()
        readonly.chmod(0o555)
        try:
            if os.geteuid() != 0:
                rejected(lambda: run(readonly / 'run', 5))
        finally:
            readonly.chmod(0o755)
        # The wrapper can exit before Unity; its remaining child must still be stopped.
        script = "import subprocess,pathlib,os; p=subprocess.Popen(['sleep','60']); pathlib.Path(os.environ['OUTPUT_DIR'],'pid').write_text(str(p.pid)); raise SystemExit(9)"
        orphan = base / 'orphan'
        assert run(orphan, 5, [sys.executable, '-c', script]) == 9
        pid = int((orphan / 'pid').read_text())
        for _ in range(20):
            try: os.kill(pid, 0)
            except ProcessLookupError: break
            time.sleep(0.1)
        else: raise AssertionError('child process survived cleanup')
    print('Artifact validation, startup failure, output guards, and child cleanup passed')


if __name__ == '__main__':
    if sys.argv[1:] == ['--fake']:
        fixtures(os.environ['OUTPUT_DIR'])
    else:
        main()
