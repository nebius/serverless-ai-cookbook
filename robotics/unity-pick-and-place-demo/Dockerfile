FROM ros:humble-ros-base-jammy@sha256:860e53793ccf575e5369b5e9a19939de2bfcfb46a299954d06f54f2af54fed19
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip git ffmpeg xserver-xorg-core mesa-utils libgl1-mesa-dri libglx-mesa0 \
    libglu1-mesa libgtk-3-0 libnss3 libasound2 libxrandr2 libxcursor1 \
    libxi6 libxinerama1 libxss1 ros-humble-trajectory-msgs ros-humble-rosbag2 \
    && rm -rf /var/lib/apt/lists/*
RUN pip3 install --no-cache-dir numpy==1.26.4 onnxruntime==1.23.2 pillow==10.4.0
WORKDIR /ros_ws
RUN git init src/ros_tcp_endpoint && git -C src/ros_tcp_endpoint fetch --depth 1 \
    https://github.com/Unity-Technologies/ROS-TCP-Endpoint.git 54c1a64b6d5ef6ffa0a0431570bb74329b79b15b \
    && git -C src/ros_tcp_endpoint checkout --detach FETCH_HEAD \
    && . /opt/ros/humble/setup.sh && colcon build
WORKDIR /app
COPY build/ /app/player/
RUN test -f player/UnityRobot.x86_64 && test -f player/UnityPlayer.so \
    && test -d player/UnityRobot_Data && test -f player/build.json \
    && chmod +x player/UnityRobot.x86_64 \
    && ! ldd player/UnityRobot.x86_64 | grep 'not found' \
    && ! ldd player/UnityPlayer.so | grep 'not found'
COPY runtime/pick-policy/ /app/policy/
COPY runtime/pick-kinematics.json runtime/pick_kinematics.py /app/
COPY runtime/run.py runtime/policy_node.py runtime/perception.py runtime/xorg.conf check.py /app/
ENV RUN_SECONDS=180 OUTPUT_DIR=/results/demo NVIDIA_DRIVER_CAPABILITIES=all ROS_LOCALHOST_ONLY=1
ENTRYPOINT ["/ros_entrypoint.sh", "bash", "-c", "source /ros_ws/install/setup.bash && exec python3 /app/run.py"]
