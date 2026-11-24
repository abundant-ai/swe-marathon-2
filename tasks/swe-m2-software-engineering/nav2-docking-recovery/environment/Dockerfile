FROM ubuntu:24.04

COPY install_jazzy.sh /tmp/install_jazzy.sh
RUN sh /tmp/install_jazzy.sh \
    && python3 -m venv /opt/agent-helpers \
    && /opt/agent-helpers/bin/pip install --no-cache-dir uv==0.7.13 \
    && useradd --create-home --user-group candidate \
    && install -d -o candidate -g candidate /app /app/dock_recovery

ENV PATH=/opt/agent-helpers/bin:/usr/local/bin:/usr/bin:/bin \
    AMENT_PREFIX_PATH=/opt/ros/jazzy \
    PYTHONPATH=/opt/ros/jazzy/lib/python3.12/site-packages \
    LD_LIBRARY_PATH=/opt/ros/jazzy/lib:/opt/ros/jazzy/lib/x86_64-linux-gnu \
    RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST \
    CYCLONEDDS_URI="<CycloneDDS><Domain Id='any'><General><Interfaces><NetworkInterface name='lo'/></Interfaces><AllowMulticast>false</AllowMulticast></General><Discovery><Peers><Peer Address='127.0.0.1'/></Peers><ParticipantIndex>auto</ParticipantIndex></Discovery></Domain></CycloneDDS>"

COPY example /app/example
WORKDIR /app
