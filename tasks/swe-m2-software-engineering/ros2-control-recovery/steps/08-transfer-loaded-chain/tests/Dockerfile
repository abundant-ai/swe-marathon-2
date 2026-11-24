FROM ubuntu:24.04

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl cmake g++ make \
    && curl --fail --silent --show-error --location \
       https://raw.githubusercontent.com/ros/rosdistro/master/ros.key -o /usr/share/keyrings/ros2-archive-keyring.gpg \
    && echo 'deb [signed-by=/usr/share/keyrings/ros2-archive-keyring.gpg] https://repo.ros2.org/ubuntu/main noble main' \
       > /etc/apt/sources.list.d/ros2.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
       ros-jazzy-ament-cmake ros-jazzy-rclpy ros-jazzy-rmw-cyclonedds-cpp \
       ros-jazzy-controller-manager ros-jazzy-hardware-interface ros-jazzy-controller-interface \
       ros-jazzy-joint-state-broadcaster ros-jazzy-forward-command-controller ros-jazzy-control-msgs \
    && rm -rf /var/lib/apt/lists/*

ENV ROS_JAZZY_PREFIX=/opt/ros/jazzy RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \
    CYCLONEDDS_URI="<CycloneDDS><Domain Id='any'><General><Interfaces><NetworkInterface name='lo'/></Interfaces><AllowMulticast>false</AllowMulticast></General><Discovery><Peers><Peer Address='127.0.0.1'/></Peers><ParticipantIndex>auto</ParticipantIndex></Discovery></Domain></CycloneDDS>"

RUN useradd --uid 10001 --create-home --user-group candidate \
    && install -d -m 0700 /tests /logs/verifier
COPY *.py test.sh /tests/
RUN chmod 0700 /tests/test.sh
WORKDIR /app

COPY lift_device /tests/lift_device
RUN . /opt/ros/jazzy/setup.sh \
    && cmake -S /tests/lift_device -B /tmp/lift-build \
       -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/opt/lift-device \
    && cmake --build /tmp/lift-build --target install -j 2 \
    && rm -rf /tmp/lift-build
ENV ROS_LIFT_DEVICE_PREFIX=/opt/lift-device
