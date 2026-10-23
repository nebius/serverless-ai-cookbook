"""Run one Unity player, make a preview, and save checked artifacts."""
import json
import math
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

from check import check, measurements, frame_timing, task_measurements


def stop(process):
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            break
        except PermissionError:
            if sys.platform != 'darwin': raise
            process.wait(timeout=5)
            return
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            process.poll()
            try:
                os.killpg(process.pid, 0)
            except ProcessLookupError:
                process.wait()
                return
            except PermissionError:
                # macOS can report EPERM for a just-emptied process group.
                if sys.platform != "darwin":
                    raise
                process.wait(timeout=5)
                return
            time.sleep(0.1)
    process.wait()


def encode_preview(root):
    times,duration,fps=frame_timing(root)
    # Retain real capture times if rendering drops frames; never speed up the simulation.
    lines=['ffconcat version 1.0']
    for i,stamp in enumerate(times):
        end=times[i+1] if i+1<len(times) else duration
        lines += [f"file 'images/frame_{i:05d}.png'",f'duration {max(end-stamp,1e-6):.9f}']
    lines += [f"file 'images/frame_{len(times)-1:05d}.png'"]
    (root/'preview.ffconcat').write_text('\n'.join(lines)+'\n')
    with (root/'ffmpeg.log').open('w') as log:
        subprocess.run(['ffmpeg','-nostdin','-v','error','-f','concat','-safe','0',
            '-i',str(root/'preview.ffconcat'),'-t',str(duration-times[0]),'-r',str(fps),
            '-c:v','libx264','-pix_fmt','yuv420p',str(root/'preview.mp4')],
            check=True,stdout=log,stderr=subprocess.STDOUT,timeout=120)


def run(output, seconds, command=None):
    if not math.isfinite(seconds) or not 5 <= seconds <= 600:
        raise ValueError("RUN_SECONDS must be between 5 and 600")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    # Probe the mount before starting Unity; an existing prefix is never overwritten.
    (output / "write-probe").write_text("writable")
    (output / "write-probe").unlink()
    result = {"success": False, "requested_seconds": seconds}
    process = None
    children = []
    logs = []
    exit_code = 1
    with tempfile.TemporaryDirectory(prefix="unity-") as temporary:
        local = Path(temporary)
        environment = dict(os.environ, DISPLAY=':99', RUN_SECONDS=str(seconds), OUTPUT_DIR=str(local), POLICY_CONFIG=str(local / 'targets.json'))
        metadata = json.loads(Path('/app/policy/metadata.json').read_text()) if command is None else None
        if metadata:
            (local / 'targets.json').write_text(json.dumps({'joint_names': metadata['joint_names'],
                'task':'pick_place'}))
            shutil.copyfile('/app/policy/metadata.json', local / 'policy-metadata.json')
        def launch(name, args):
            log = (local / f'{name}.log').open('w'); logs.append(log)
            child = subprocess.Popen(args, env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            children.append(child)
            return child
        def alive():
            for child in children:
                if child.poll() is not None:
                    raise subprocess.CalledProcessError(child.returncode or 1, child.args)
        try:
            if command is None:
                launch('display',['Xorg',':99','-config','/app/xorg.conf','-noreset','-nolisten','tcp',
                    '-logfile',str(local/'xorg.log')])
                deadline=time.monotonic()+30
                while True:
                    alive()
                    probe=subprocess.run(['glxinfo','-B'],env=environment,capture_output=True,text=True,timeout=5)
                    if probe.returncode==0:
                        (local/'graphics.log').write_text(probe.stdout)
                        if 'NVIDIA' not in probe.stdout: raise ValueError('NVIDIA GPU rendering unavailable')
                        break
                    if time.monotonic()>deadline: raise TimeoutError('NVIDIA display not ready; inspect xorg.log')
                    time.sleep(.2)
                launch('endpoint', ['ros2', 'run', 'ros_tcp_endpoint', 'default_server_endpoint',
                    '--ros-args', '-p', 'ROS_IP:=127.0.0.1', '-p', 'ROS_TCP_PORT:=10000'])
                deadline = time.monotonic() + 30
                while True:
                    alive()
                    try:
                        with socket.create_connection(('127.0.0.1',10000), timeout=.2): break
                    except OSError:
                        if time.monotonic() > deadline: raise TimeoutError('TCP endpoint not ready')
                        time.sleep(.2)
                launch('rosbag', ['ros2','bag','record','-o',str(local/'rosbag'),
                    '/joint_states','/tool_position','/tool_pose','/goal','/joint_commands',
                    '/camera/image/compressed','/gripper_command','/gripper_contacts','/cube_ground_truth','/task_phase'])
                launch('policy', ['python3','/app/policy_node.py'])
                time.sleep(2); alive()
            with (local / "unity.log").open("w") as log:
                process = subprocess.Popen(command or ["/app/player/UnityRobot.x86_64", "-batchmode", "-force-glcore", "-logFile", "-"],
                    env=environment, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                deadline = time.monotonic() + seconds + 90
                while process.poll() is None:
                    alive()
                    if time.monotonic() > deadline: raise subprocess.TimeoutExpired(process.args,seconds+90)
                    time.sleep(.2)
                for child in reversed(children): stop(child)
                children.clear()
                for log in logs: log.close()
                if process.returncode != 0:
                    raise subprocess.CalledProcessError(process.returncode, process.args)
            pixels = subprocess.run(["ffmpeg", "-v", "error", "-i", str(local / "images/frame_00000.png"),
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], check=True, capture_output=True, timeout=30).stdout
            if not pixels or all(len(set(pixels[channel::3])) <= 1 for channel in range(3)):
                raise ValueError("camera rendered a uniform image; inspect unity.log")
            encode_preview(local)
            if not (local/'renderer.json').is_file():
                raise ValueError('Missing Unity GPU renderer receipt')
            result.update(task_measurements(local), task='pick_place')
            result.update(measurements(local), image_count=len(list((local / "images").glob("frame_*.png"))))
            result["success"] = True
            (local / "result.json").write_text(json.dumps(result, indent=2) + "\n")
            check(local)
            exit_code = 0
        except Exception as error:
            result.update(success=False, error=str(error))
            if isinstance(error, subprocess.CalledProcessError):
                exit_code = error.returncode if error.returncode > 0 else 128 - error.returncode
        finally:
            for child in reversed(children): stop(child)
            for log in logs: log.close()
            if process is not None:
                stop(process)
            try:
                # Publish the receipt only after every artifact has copied and passed verification.
                for source in local.rglob("*"):
                    if source.is_file() and source != local/'result.json':
                        destination = output / source.relative_to(local)
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(source, destination)
                if exit_code == 0:
                    check(output, result=result)
            except Exception as error:
                result.update(success=False, error=(result.get('error','')+f"\nArtifact publication failed: {error}").strip())
                exit_code = exit_code or 1
            try:
                (output/'result.json').write_text(json.dumps(result,indent=2)+"\n")
            except OSError as error:
                result.update(success=False, error=(result.get('error','')+f"\nResult publication failed: {error}").strip())
                exit_code = exit_code or 1
    print(json.dumps(result, indent=2), flush=True)
    return exit_code


if __name__ == "__main__":
    try:
        raise SystemExit(run(os.environ["OUTPUT_DIR"], float(os.environ.get("RUN_SECONDS", "180"))))
    except (KeyError, ValueError, OSError) as error:
        raise SystemExit(f"Unity demo failed: {error}")
