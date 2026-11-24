"""Independently observe native trajectory evidence and two moving robot footprints."""

from collections import Counter
from functools import lru_cache
import json
from math import dist, hypot
import os
from pathlib import Path
import pwd
import select
import signal
import subprocess
import sys
from time import monotonic

from fleet_world import PhysicalConflict, Rejected, require


PERIOD_NS=250_000_000
CASES=(
    ("mirror_gap_and_retained_physical_crossing",1,"gap"),
    ("restart_and_replaced_carrier_plan", -1,"restart"),
    ("occupied_corridor_requires_useful_bypass",1,"bypass"),
)


def executable(name):
    local=os.environ.get("FLEET_RMF_NATIVE")
    if local and name=="rmf-native":
        return local
    return f"/usr/local/bin/{name}"


def geometry(args, records):
    """Use the supervisor-owned compiled native library adapter."""
    text="".join(" ".join(map(str,row))+"\n" for row in records)
    completed=subprocess.run([executable("rmf-native"),args],input=text,text=True,
                               capture_output=True,timeout=3,check=True)
    return completed.stdout.strip().splitlines()


@lru_cache(maxsize=40)
def expected_points(profile, poses):
    response=geometry("interpolate",[[*profile,len(poses)],*poses])
    return tuple((int(line.split()[0]),*map(float,line.split()[1:])) for line in response[1:])


@lru_cache(maxsize=50)
def expected_collision(map_name,profile_a,points_a,start,profile_b,points_b,request_begin):
    observed=geometry("conflict",[[map_name,profile_a[0],len(points_a)],
                    *((start+stamp,*row) for stamp,*row in points_a),
                    [map_name,profile_b[0],len(points_b)],
                    *((request_begin+stamp,*row) for stamp,*row in points_b)])
    return None if observed[0]=="clear" else int(observed[0])


def registered(profile):
    keys=("radius","linear_speed","linear_accel","angular_speed","angular_accel")
    return dict(zip(keys,profile,strict=True))


class Driver:
    """Submit the real durable candidate session under an unprivileged account."""

    def __init__(self,app,path,spec):
        path.mkdir()
        self.app=app
        self.spec=path/"spec.json"
        self.spec.write_text(json.dumps(spec))
        self.state=path/"state"
        self.state.mkdir(mode=0o777)
        self.state.chmod(0o777)
        self.start()

    def start(self):
        name="candidate"
        try:
            user=pwd.getpwnam(name)
        except KeyError:
            user=pwd.getpwnam("nobody")
        identity={"user":user.pw_uid,"group":user.pw_gid,"extra_groups":[]} if os.geteuid()==0 else {}
        environment={"PATH":os.environ.get("PATH","/usr/bin:/bin"),"HOME":str(self.state),
                     "LC_ALL":"C.UTF-8","FLEET_RMF_NATIVE":executable("rmf-native")}
        self.process=subprocess.Popen([sys.executable,"-B","-m","fleet_recovery","rmf-handover",
                                      "--spec",str(self.spec),"--state",str(self.state)],
                                     cwd=self.app,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL,start_new_session=True,env=environment,**identity)
        self.buffer=b""

    def exchange(self,event):
        try:
            self.process.stdin.write(json.dumps(event,allow_nan=False).encode()+b"\n")
            self.process.stdin.flush()
        except BrokenPipeError:
            raise Rejected("coordinator exited before reading native event") from None
        deadline=monotonic()+3
        pipe=self.process.stdout.fileno()
        while b"\n" not in self.buffer:
            require(select.select([pipe],[],[],max(deadline-monotonic(),0))[0],"native handover did not flush reply")
            chunk=os.read(pipe,65536)
            require(chunk and len(self.buffer)+len(chunk)<150000,"coordinator exited or returned an oversized reply")
            self.buffer+=chunk
        row,self.buffer=self.buffer.split(b"\n",1)
        return json.loads(row)

    def close(self):
        try:
            os.killpg(self.process.pid,signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.process.wait()
        self.process.stdin.close()
        self.process.stdout.close()

    def restart(self):
        self.close()
        self.start()


class Scene:
    """Run a read-only route and a separately actuated courier over a small passage."""

    def __init__(self,direction,kind):
        self.direction=direction
        self.kind=kind
        self.pa=(.37,.65,.54,.65,.47)
        self.pb=(.32,.84,.6,.7,.5)
        self.vel=.65
        self.start_time=9.55 if kind=="bypass" else 5.95
        self.xmin,self.xmax=-3.12,3.22
        self.yaw=0.0 if direction==1 else 3.141592653589793
        self.initial_plan=self.poses(self.xmin)
        self.current_pose=(0.0,-2.65)
        self.node="loading"
        self.pending=None
        self.receipt=None
        self.commands={}
        self.moves=[]
        self.measured_minimum=100.0
        self.done_at=None
        self.route_version=1
        self.active_plan=61+direction
        self.last_good_capture=None
        self.expected_mirror=None
        self.outcomes=Counter()
        self.guard_authority_tick=None

    def poses(self,first):
        choices=[first,*[x for x in (-.74,1.16,2.05,self.xmax) if x>first]]
        return [[x*self.direction,0.0,self.yaw] for x in choices]

    def manifest(self):
        nodes={"loading":[0.0,-2.65],"bay":[0.0,-1.20],"delivery":[0.0,1.68]}
        links=[("loading","bay",False),("bay","delivery",True)]
        if self.kind=="bypass":
            nodes.update({"outer_entry":[4.38,-1.20],"outer_exit":[4.38,1.68]})
            links.extend((("bay","outer_entry",False),("outer_entry","outer_exit",False),
                          ("outer_exit","delivery",False)))
        return {"map":"office-floor","carrier_profile":registered(self.pa),"courier_profile":registered(self.pb),
                "start_node":"loading","goal_node":"delivery","nodes":nodes,"crossing":{"axis":0,
                "sign":self.direction,"clear_progress_m":.78},"carrier_lane_tolerance_m":.11,
                "telemetry_max_age_ns":760_000_000,"settle_tolerance_m":.046,
                "probe":{"start_ns":8_500_000_000,"poses":[[0,-2.65,1.5707963267948966],[0,1.68,1.5707963267948966]]},
                "edges":[{"from":a,"to":b,"requires_clearance":guarded} for a,b,guarded in links]}

    def carrier(self, seconds):
        length = self.xmax - self.xmin
        traveled = max(0.0, seconds - self.start_time) * self.vel
        position = self.xmax if traveled >= length else self.xmin + traveled
        return self.direction * position, 0.0

    def schedule(self,tick):
        plan_base={"kind":"snapshot","version":1,"plan_id":61+self.direction,"start_ns":0,"poses":self.initial_plan}
        if tick==0:
            return plan_base,1
        if self.kind=="gap":
            if tick==11:
                return {"kind":"delta","base_version":2,"version":3,"delay_ns":1_200_000_000},3
            if tick==12:
                return plan_base,3
            if tick==22:
                return plan_base|{"version":3,"start_ns":5_950_000_000},3
            return None,3 if tick>=11 else 1
        if tick==12:
            return {"kind":"delta","base_version":1,"version":2,"delay_ns":5_950_000_000},2
        if self.kind=="restart" and tick==36:
            actual=self.carrier(tick*PERIOD_NS/1e9)[0]*self.direction
            self.active_plan=714
            return {"kind":"snapshot","version":3,"plan_id":714,"start_ns":tick*PERIOD_NS,
                    "poses":self.poses(actual)},3
        wanted=3 if self.kind=="restart" and tick>=36 else 2 if tick>=12 else 1
        return None,wanted

    def event(self,tick):
        now=tick*PERIOD_NS
        patch,required=self.schedule(tick)
        A=self.carrier(now/1e9)
        carrier={"plan_id":self.active_plan,"capture_ns":now,"position":list(A),
                 "vendor_remaining":0 if 16<tick<37 else 4}
        if self.kind=="restart" and tick in (36,37,38):
            carrier={"plan_id":61+self.direction,"capture_ns":now,"position":[self.xmax*self.direction,0.0],
                     "vendor_remaining":0}
        elif self.kind=="gap" and 25<=tick<=30:
            if tick==25:
                carrier["capture_ns"]=now+PERIOD_NS
                carrier["position"]=[self.xmax*self.direction,0.0]
            else:
                carrier=None
        elif self.kind=="bypass" and tick==18:
            carrier["capture_ns"]=now-2*PERIOD_NS
            carrier["position"]=[self.xmax*self.direction,0.0]
        settled=self.receipt
        if self.kind=="restart" and tick==3 and self.pending:
            settled=self.pending["id"]
        return {"tick":tick,"time_ns":now,"required_version":required,"schedule":patch,"carrier":carrier,
                "courier":{"position":list(self.current_pose),"settled":settled},"closed_edges":[]}

    def metadata(self,event,spec):
        """Maintain an independent version/capture witness for the delivered stream."""
        update=event["schedule"]
        previous=self.expected_mirror
        if update and (previous is None or update["version"]>previous["version"]):
            if update["kind"]=="snapshot":
                self.expected_mirror={field:update[field] for field in ("version","plan_id","start_ns","poses")}
            elif previous and update["base_version"]==previous["version"]:
                self.expected_mirror={**previous,"version":update["version"],
                                      "start_ns":previous["start_ns"]+update["delay_ns"]}
            else:
                self.outcomes["gap_rejected"]+=1
        current=self.expected_mirror
        record=event["carrier"]
        if current is None:
            return None,None,None,None,False
        a=expected_points(self.pa,tuple(tuple(p) for p in current["poses"]))
        if (not previous or current["plan_id"]!=previous["plan_id"]):
            self.last_good_capture=None
        now=event["time_ns"]
        if (record and record["plan_id"]==current["plan_id"] and
            0<=now-record["capture_ns"]<=spec["telemetry_max_age_ns"] and
            (self.last_good_capture is None or record["capture_ns"]>self.last_good_capture["capture_ns"])):
            self.last_good_capture=record
        if current["version"]!=event["required_version"]:
            self.outcomes["stale_view"]+=1
            return current["version"],current["plan_id"],None,None,False
        b=expected_points(self.pb,tuple(tuple(p) for p in spec["probe"]["poses"]))
        meeting=expected_collision(spec["map"],self.pa,a,current["start_ns"],self.pb,b,spec["probe"]["start_ns"])
        self.outcomes["native_forecast_conflict" if meeting is not None else "native_forecast_clear"]+=1
        sample=self.last_good_capture
        if sample is None or now-sample["capture_ns"]>spec["telemetry_max_age_ns"]:
            return current["version"],current["plan_id"],None,meeting,False
        progress=self.direction*sample["position"][0]
        reached=[i for i,p in enumerate(a) if self.direction*p[1]<=progress+1e-7]
        checkpoint=reached[-1] if reached else -1
        permitted=bool(reached and self.direction*a[checkpoint][1]>=spec["crossing"]["clear_progress_m"])
        return current["version"],current["plan_id"],checkpoint,meeting,permitted

    def consume(self,reply,tick,corridor,spec):
        cmd=reply.get("command")
        if self.pending is not None:
            require(cmd==self.pending,"changed an issued command before measured settlement")
            return
        if cmd is None:
            require(reply.get("status")==("done" if self.node=="delivery" else
                "wait_schedule" if reply["checkpoint"] is None and reply["conflict_at_ns"] is None
                and self.route_version!=reply["schedule_version"] else "wait_carrier"),
                "native state and idle mode disagreed")
            return
        require(type(cmd) is dict and set(cmd)=={"id","from","to","max_speed_mps"} and
                isinstance(cmd["id"],str) and cmd["id"] not in self.commands,
                "movement requires one new usable authority identity")
        edge=next((x for x in spec["edges"] if x["from"]==cmd["from"] and x["to"]==cmd["to"]),None)
        require(edge is not None and cmd["from"]==self.node and
                dist(self.current_pose,spec["nodes"][self.node])<.05,
                "new route does not start in the courier's physically settled place")
        require(reply["status"]=="moving" and 0<cmd["max_speed_mps"]<=self.pb[1]+1e-12,
                "movement authority exceeded the commissioned speed")
        if edge["requires_clearance"]:
            require(corridor,"granted crossing on a stale mirror or unreached native checkpoint")
            self.guard_authority_tick=tick
        self.commands[cmd["id"]]=cmd
        self.moves.append([tick,cmd["from"],cmd["to"]])
        self.receipt=None
        self.pending=cmd

    def advance(self,tick,spec):
        """Measure minimum swept pairwise separation, splitting movement at actual arrivals."""
        dt=PERIOD_NS/1e9
        for segment in range(10):
            t0=tick*dt+segment*dt/10
            t1=t0+dt/10
            b0=self.current_pose
            if self.pending:
                destination=spec["nodes"][self.pending["to"]]
                length=dist(b0,destination)
                travel=self.pending["max_speed_mps"]*(t1-t0)
                if length<=travel:
                    self.current_pose=tuple(destination)
                    self.node=self.pending["to"]
                    self.receipt=self.pending["id"]
                    self.pending=None
                elif length>0:
                    self.current_pose=tuple(x+(y-x)*travel/length for x,y in zip(b0,destination,strict=True))
            a0,a1=self.carrier(t0),self.carrier(t1)
            offset=tuple(a-b for a,b in zip(a0,b0,strict=True))
            end=tuple(a-b for a,b in zip(a1,self.current_pose,strict=True))
            displacement=tuple(q-p for p,q in zip(offset,end,strict=True))
            square=sum(v*v for v in displacement)
            projected=0 if square==0 else min(1.0,max(0.0,-sum(p*v for p,v in zip(offset,displacement,strict=True))/square))
            clearance=hypot(*(p+projected*v for p,v in zip(offset,displacement,strict=True)))-self.pa[0]-self.pb[0]
            self.measured_minimum=min(clearance,self.measured_minimum)
            if clearance<.04:
                raise PhysicalConflict(f"swept robot footprints exceeded clearance, measured {clearance:.3f} m")
            if self.node=="delivery" and self.done_at is None:
                self.done_at=t1


def check(app,root,direction,kind):
    scene=Scene(direction,kind)
    spec=scene.manifest()
    driver=Driver(app,root,spec)
    replayed=False
    try:
        for tick in range(98):
            packet=scene.event(tick)
            scene.route_version=packet["required_version"]
            version,plan,checkpoint,meeting,clear=scene.metadata(packet,spec)
            reply=driver.exchange(packet)
            require(type(reply) is dict and set(reply)=={"tick","status","schedule_version","carrier_plan",
                                                        "checkpoint","conflict_at_ns","command"} and reply["tick"]==tick,
                    "native handover response was malformed")
            require((reply["schedule_version"],reply["carrier_plan"],reply["checkpoint"])==(version,plan,checkpoint),
                    f"stale schedule or unmeasured native checkpoint at tick {tick}, got {reply}, want {(version,plan,checkpoint)}")
            require(reply["conflict_at_ns"]==meeting,f"incorrect native cubic conflict time at tick {tick}")
            if kind=="restart" and tick==3:
                require(scene.pending and reply["command"]==scene.pending and scene.node=="loading",
                        "early receipt without matching geometry settled a command")
                driver.restart()
                changed=packet|{"required_version":version+4}
                require(driver.exchange(changed)=={"tick":tick,"status":"rejected","schedule_version":None,
                        "carrier_plan":None,"checkpoint":None,"conflict_at_ns":None,"command":None},
                        "altered retry rewrote previously issued authority")
                require(driver.exchange(packet)==reply,"lost reply did not recover the exact committed command")
                replayed=True
            scene.consume(reply,tick,clear,spec)
            scene.advance(tick,spec)
            if reply["status"]=="done" and scene.done_at is not None and abs(scene.carrier(tick*.25)[0]-direction*scene.xmax)<.05:
                break
        require(scene.done_at is not None and abs(scene.carrier(tick*.25)[0]-direction*scene.xmax)<.05,
                "both physical fleets must finish their assigned routes")
        require(scene.done_at<(18.8 if kind=="bypass" else 23.2),"waiting forever lost the measured delivery deadline")
        if kind=="gap":
            require(scene.outcomes["gap_rejected"]>=1 and scene.outcomes["stale_view"]>=8 and
                    scene.outcomes["native_forecast_clear"]>=2 and scene.outcomes["native_forecast_conflict"]>=2 and
                    scene.guard_authority_tick is not None,"mirror gap, restored conflict and later handover were not exercised")
        if kind=="restart":
            require(replayed and scene.guard_authority_tick is not None and scene.guard_authority_tick>37,
                    "restart or replaced plan did not affect the release")
        if kind=="bypass":
            require(any(move[2]=="outer_exit" for move in scene.moves),"courier did not use the physically clear bypass")
        return {"courier_delivery_s":scene.done_at,"physical_clearance_m":scene.measured_minimum,
                "guard_authority_tick":scene.guard_authority_tick,"restored_receipt":replayed,
                "native_evidence":dict(scene.outcomes),"commands":scene.moves}
    finally:
        driver.close()


def native_suite(app,root):
    """Run small independently scoped two-fleet mission witnesses."""
    observations={}
    for name,direction,kind in CASES:
        try:
            result=check(app,root/name,direction,kind)
        except (Rejected,ValueError,TypeError,KeyError) as error:
            observations[name]={"passed":False,"observation":str(error),"physical_conflict":isinstance(error,PhysicalConflict)}
        else:
            observations[name]={"passed":True,"observation":result}
    return observations
