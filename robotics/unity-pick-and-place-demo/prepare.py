"""Fetch the public robot project and install the cookbook scripts."""
import argparse
from pathlib import Path
import shutil
import subprocess

REVISION = "111705a8a4417fb7fe1816f46daa67ef01342464"
EDITOR_VERSION = "6000.6.5f1"

def prepare(destination):
    destination = Path(destination)
    if destination.exists():
        raise ValueError(f"{destination} exists; use a fresh directory")
    subprocess.run(["git", "init", str(destination)], check=True)
    subprocess.run(["git", "-C", str(destination), "fetch", "--depth", "1",
                    "https://github.com/Unity-Technologies/articulations-robot-demo.git", REVISION], check=True)
    subprocess.run(["git", "-C", str(destination), "checkout", "--detach", "FETCH_HEAD"], check=True)
    scripts = destination / "ArmRobot/Assets/Cookbook"
    (scripts / "Editor").mkdir(parents=True)
    source = Path(__file__).parent / "unity"
    shutil.copyfile(source / "packages.json", destination / "ArmRobot/Packages/manifest.json")
    (destination / "ArmRobot/Packages/packages-lock.json").unlink(missing_ok=True)
    shutil.copyfile(source / "DemoRun.cs", scripts / "DemoRun.cs")
    shutil.copyfile(source / "PickScene.cs", scripts / "PickScene.cs")
    shutil.copyfile(source / "DemoBuild.cs", scripts / "Editor/DemoBuild.cs")
    settings = destination / "ArmRobot/ProjectSettings/ProjectSettings.asset"
    text = settings.read_text()
    text = text.replace("scriptingDefineSymbols: {}", "scriptingDefineSymbols:\n    1: ROS2")
    settings.write_text(text)
    print(f"Open {destination.resolve() / 'ArmRobot'} using Unity {EDITOR_VERSION}; see README.md")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", nargs="?", default="project")
    prepare(parser.parse_args().destination)
