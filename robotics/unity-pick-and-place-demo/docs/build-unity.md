# Build the Unity player

This is a one-time setup. Run commands from the cookbook directory.

| Component | Pin |
|---|---|
| [Articulations Robot Demo](https://github.com/Unity-Technologies/articulations-robot-demo), linked by [Robotics Hub](https://github.com/Unity-Technologies/Unity-Robotics-Hub/blob/main/ARCHIVE.md) | `111705a8a4417fb7fe1816f46daa67ef01342464` |
| Unity Editor / Linux Mono player | `6000.6.5f1` |
| [ROS TCP Connector](https://github.com/Unity-Technologies/ROS-TCP-Connector) | `c27f00c6cf750d2d0564349b3039d19aa3925e7c` |
| [ROS TCP Endpoint](https://github.com/Unity-Technologies/ROS-TCP-Endpoint/tree/main-ros2) | `54c1a64b6d5ef6ffa0a0431570bb74329b79b15b` |
| Runtime | Ubuntu 22.04, ROS 2 Humble, ONNX Runtime 1.23.2 |

## Install the Editor

In Unity Hub, activate your Unity license and install Editor **6000.6.5f1** with
**Linux Build Support (Mono)**. If the Editor is already installed, use its
module settings to add Linux support. Point `UNITY_EDITOR` at the Editor
executable, rather than Unity Hub.

You can open the prepared `project/ArmRobot` folder in that Editor to inspect the
scene. No manual scene changes are needed for the demo; the build script prepares
it automatically. Close the project in the Editor before the batch build.

## Prepare and build

The robot assets, ROS and shipped weights are public and ungated. The first build
requires a licensed Unity Editor with Linux Build Support (Mono); the Editor and
credentials stay outside the container. Running a built image needs no Unity
account. Nebius compute/storage require an existing account and incur charges.

From this directory:

```bash
python3 prepare.py
export UNITY_EDITOR='/path/to/Unity/Editor/Unity'
# macOS: /Applications/Unity/Hub/Editor/6000.6.5f1/Unity.app/Contents/MacOS/Unity
export UNITY_BUILD_DIR="$PWD/build"
"$UNITY_EDITOR" -batchmode -quit -projectPath "$PWD/project/ArmRobot" \
  -executeMethod DemoBuild.Linux -logFile "$PWD/build.log"
```

Preparation pins the robot and connector, enables `ROS2`, and adds the unattended
scene components. The project and build directories must be fresh. Keep the
complete player: executable, `UnityPlayer.so`, `UnityRobot_Data/` and `build.json`.
Use Standalone Linux x86-64 with graphics retained; do not use `-nographics` or
strip rendering. Apple Silicon emulation cannot run this Mono player; test on
native Linux x86-64 with an NVIDIA GPU and NVIDIA Container Toolkit, or Nebius.

Return to [the tutorial](../README.md#2-build-and-push-the-container) to package the player.
