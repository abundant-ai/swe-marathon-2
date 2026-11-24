FROM ubuntu:24.04

COPY requirements.txt /opt/requirements.txt
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl python3-venv \
    && curl --fail --silent --show-error --location \
        https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros2-archive-keyring.gpg \
    && echo 'deb [signed-by=/usr/share/keyrings/ros2-archive-keyring.gpg] https://repo.ros2.org/ubuntu/main noble main' \
        > /etc/apt/sources.list.d/ros2.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends ros-jazzy-rclpy ros-jazzy-rmw-cyclonedds-cpp \
        ros-jazzy-tf2-msgs ros-jazzy-geometry-msgs ros-jazzy-std-msgs ros-jazzy-sensor-msgs \
        ros-jazzy-rosgraph-msgs ros-jazzy-rosidl-runtime-py \
    && python3 -m venv --system-site-packages /opt/bag-runtime \
    && /opt/bag-runtime/bin/pip install --no-cache-dir --only-binary=:all: -r /opt/requirements.txt \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --create-home --user-group candidate

ENV PATH=/opt/bag-runtime/bin:/usr/local/bin:/usr/bin:/bin \
    ROS_JAZZY_PREFIX=/opt/ros/jazzy AMENT_PREFIX_PATH=/opt/ros/jazzy \
    PYTHONPATH=/opt/ros/jazzy/lib/python3.12/site-packages \
    LD_LIBRARY_PATH=/opt/ros/jazzy/lib:/opt/ros/jazzy/lib/x86_64-linux-gnu \
    RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \
    CYCLONEDDS_URI="<CycloneDDS><Domain Id='any'><General><Interfaces><NetworkInterface name='lo'/></Interfaces><AllowMulticast>false</AllowMulticast></General><Discovery><Peers><Peer Address='127.0.0.1'/></Peers><ParticipantIndex>auto</ParticipantIndex></Discovery></Domain></CycloneDDS>"

RUN install -d -o candidate -g candidate /app
COPY resources/ /app/examples/
WORKDIR /app
