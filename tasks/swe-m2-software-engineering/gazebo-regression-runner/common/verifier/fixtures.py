"""Independent SDF worlds, declared fixtures and trajectory state shapes."""

from cmath import exp,phase


def rotate(a):
    """Represent planar yaw as an orientation phasor."""
    return exp(1j*a)


def combine(a,b):
    """Compose independently encoded points via complex rotation."""
    pos=complex(a[0],a[1])+complex(b[0],b[1])*rotate(a[3])
    return [pos.real,pos.imag,a[2]+b[2],phase(rotate(a[3]+b[3]))]


def xml_pose(p):
    """Encode a planar metric tuple in SDF pose syntax."""
    return f"{p[0]} {p[1]} {p[2]} 0 0 {p[3]}"


def scene(mode):
    """Generate two calibration contexts and a relative SDF frame chain."""
    n=1 if mode else 0
    dt=0.04 if n else 0.02
    anchor=[0.17,-0.14,0.25,-0.36] if n else [0.20,-0.1,0.24,0.21]
    body_local=[0.03,0.04,0.0,0.16] if n else [0.0,0.0,0.0,0.0]
    robot=f"vehicle-{n}"
    load=f"pallet-{n}"
    gyro=f"/rig{n}/gyro"
    beam=f"/rig{n}/beam"
    imu=[-0.03,0.02,0.035,-0.31]
    lidar=[0.21,0.0,0.01,0.0]
    box=[1.50,0.16,anchor[2],0.21]
    rover_size=[0.36,0.26,0.20]
    box_size=[0.24,0.68,0.32]
    base=combine(anchor,body_local)
    def model_shape(side):
        """Encode a supported collision geometry declaration."""
        return f'<collision name="shell"><geometry><box><size>{" ".join(map(str,side))}</size></box></geometry></collision>'
    world=f"""<sdf version="1.9"><world name="private-portable"><physics name="runner"><max_step_size>{dt}</max_step_size></physics>
    <frame name="late-frame"><pose relative_to="mount">{xml_pose([0.31,-0.21,0.04,0.37])}</pose></frame>
    <frame name="mount"><pose>{xml_pose(anchor)}</pose></frame>
    <model name="{robot}"><pose relative_to="mount">{xml_pose(body_local)}</pose>
      <link name="base">{model_shape(rover_size)}
        <sensor name="imu" type="imu"><pose>{xml_pose(imu)}</pose><topic>{gyro}</topic><update_rate>{1/(2*dt)}</update_rate></sensor>
        <sensor name="lidar" type="gpu_lidar"><pose>{xml_pose(lidar)}</pose><topic>{beam}</topic><update_rate>{1/(5*dt)}</update_rate></sensor>
      </link></model>
    <model name="{load}"><static>true</static><pose>{xml_pose(box)}</pose><link name="obstacle">{model_shape(box_size)}</link></model>
    </world></sdf>"""
    frames={"world":[0,0,0,0],"mount":anchor,"late-frame":combine(anchor,[0.31,-0.21,0.04,0.37]),
            robot:base,f"{robot}::base":base,f"{robot}::base::imu":combine(base,imu),
            f"{robot}::base::lidar":combine(base,lidar),load:box,f"{load}::obstacle":box}
    fixture={"dt":dt,"base":base,"box":box,"rover_size":rover_size,"box_size":box_size,"robot":robot,"load":load,
             "sensors":{gyro:{"type":"imu","period_steps":2,"frame":f"{robot}::base::imu","relative":imu},
                        beam:{"type":"gpu_lidar","period_steps":5,"frame":f"{robot}::base::lidar","relative":lidar}},
             "frames":frames}
    reset=37 if not n else 23
    run={"steps":63 if not n else 45,"robot":robot,"mass_kg":1.45 if not n else 1.82,
         "damping":0.44 if not n else 0.62,"seed":293+128*n,"reset_steps":[reset],
         "commands":[{"step":0,"force_n":4.7,"torque_nm":0.005 if n else 0},
                     {"step":reset+5,"force_n":1.7,"torque_nm":0.06}],
         "relocations":[{"step":6 if n else 12,"model":load,"pose":[0.92,base[1]+0.10,base[2],0.20],"jitter_m":0.018}],
         "qos":{gyro:"best_effort",beam:"reliable"}}
    return world,fixture,run
