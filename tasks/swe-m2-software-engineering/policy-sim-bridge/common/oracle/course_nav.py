"""Choose a navigation lease and run the frozen walking policy with it."""

import json
from math import hypot
from pathlib import Path
import sys

from .course_planner import Site, heading, pursuit_twist
from .locomotion import Deployment, canonical, commit, integer, number, vector


def estimate_pose(raw, prior, tick, maximum_age):
    """Pick the newest valid surveyed localization observation."""
    if not isinstance(raw, dict):
        return prior
    try:
        capture = integer(raw['capture_tick'], 'localization capture')
        position = vector(raw['position'], 2, 'survey position')
        angle = number(raw['heading_rad'], 'body heading')
        velocity = vector(raw['velocity'], 2, 'survey velocity')
    except (KeyError, ValueError):
        return prior
    if not tick-maximum_age <= capture <= tick or (prior and capture <= prior['capture_tick']):
        return prior
    return {'capture_tick': capture,'position':position,'heading_rad':angle,'velocity':velocity}


def accept_map(raw, previous, tick, course):
    """Reject outdated snapshots while allowing a current revision to renew its lease."""
    if not isinstance(raw, dict):
        return previous
    try:
        revision = integer(raw['revision'], 'map revision')
        capture = integer(raw['capture_tick'], 'map capture')
        expiry = integer(raw['valid_until_tick'], 'map expiry')
        obstacles = [vector(row,4,'axis-aligned bounds') for row in raw['obstacles']]
        if any(a >= b or c >= d for a,b,c,d in obstacles):
            return previous
    except (KeyError, TypeError, ValueError):
        return previous
    if not tick-course['max_map_age_ticks'] <= capture <= tick or not tick <= expiry <= capture + course['max_map_lease_ticks']:
        return previous
    if previous and (revision < previous['revision'] or capture <= previous['capture_tick']
                     or (revision == previous['revision'] and previous['obstacles'] != obstacles)):
        return previous
    return {'revision': revision,'capture_tick': capture,'valid_until_tick':expiry,'obstacles':obstacles}


class Navigator:
    """Control a measured clearance path without transferring stale motion authority."""

    def __init__(self, manifest):
        raw = json.loads(manifest.read_text(encoding='utf-8'))
        self.course = raw['course']
        self.goal = vector(self.course['goal'],3,'inspection goal')
        self.extent = vector(self.course['extent'],4,'site extent')
        self.radius = number(self.course['footprint_radius_m'],'footprint radius')
        self.speed = number(self.course['max_speed_mps'],'maximum planar speed')
        if not 0 < self.radius < 2 or not 0 < self.speed <= 1:
            raise ValueError('Unsupported course radius or speed')
        self.deployment = Deployment(manifest)

    def initial(self):
        return {'actor':self.deployment.initial(),'map':None,'pose':None,'path':[],
                'request':None,'response':None}

    def move(self, tick, pose, current_map, path, changed):
        """Select a safe lookahead or hold when there is no fresh route."""
        halt = ('hold',[0.,0.,0.],[])
        if pose is None or current_map is None or tick-pose['capture_tick'] > self.course['max_pose_age_ticks']:
            return halt
        if tick > current_map['valid_until_tick'] or tick-current_map['capture_tick'] > self.course['max_map_age_ticks']:
            return halt
        position = pose['position']
        yaw = pose['heading_rad']
        square = sum((a-b)**2 for a,b in zip(self.goal[:2],position,strict=True))
        # Wait with a balance target after entering the terminal acceptance window.
        if square < .107**2 and abs(heading(self.goal[2]-yaw)) < .12:
            return 'arrived',[0.,0.,0.],path
        site = Site(self.extent,current_map['obstacles'],self.radius+.05,.15)
        if not site.clear(position):
            # Feedback can leave the extra tracking margin without crossing the physical footprint.
            # Re-enter the planning envelope through a short, independently clear retreat.
            physical=Site(self.extent,current_map['obstacles'],self.radius+.01,.15)
            x,y=site.key(position)
            cells=[site.at((x+dx,y+dy)) for dx in range(-3,4) for dy in range(-3,4)]
            retreat=[cell for cell in cells if site.clear(cell) and physical.visible(position,cell)]
            if not retreat:
                return halt
            point=min(retreat,key=lambda other:hypot(other[0]-position[0],other[1]-position[1]))
            intent=pursuit_twist(position,pose['velocity'],yaw,point,0.,min(.23,self.speed))
            return 'navigate',intent,[]
        if changed or not path or tick % 10 == 0:
            path=site.route(position,self.goal[:2])
        advance=site.pursuit(position,path) if path else None
        if advance is None:
            route=site.route(position,self.goal[:2])
            advance=site.pursuit(position,route) if route else None
            if advance is None:
                return halt
            path=route
        yaw_goal=self.goal[2] if square < .64 else 0.
        twist=pursuit_twist(position,pose['velocity'],yaw,advance,yaw_goal,self.speed)
        return 'navigate',twist,path

    def step(self, packet, state):
        """Commit both the navigation route and the corresponding actor state."""
        tick=integer(packet['tick'],'tick')
        previous=state['actor']['tick']
        contents=canonical(packet)
        if tick == previous and contents == state['request']:
            return state['response'],state
        if tick != previous + 1:
            return {'tick':tick,'mode':'rejected','lease':None,'support':[],
                    'effective_twist':None,'action':None,'target_rad':None},state
        observed_pose=estimate_pose(packet['localization'],state['pose'],tick,self.course['max_pose_age_ticks'])
        old_map=state['map']
        current_map=accept_map(packet['map'],old_map,tick,self.course)
        changed=old_map is None or current_map['revision'] != old_map['revision']
        mode,velocity,path=self.move(tick,observed_pose,current_map,state['path'],changed)
        intent={'sequence':tick,'valid_until_tick':tick+1,'velocity':velocity}
        output,actor=self.deployment.step({**packet,'request':intent},state['actor'])
        response={**output,'navigation':mode,'map_revision':current_map['revision'] if current_map else None,
                  'intent':intent}
        return response,{'actor':actor,'map':current_map,'pose':observed_pose,'path':path,
                         'request':contents,'response':response}


def navigate(spec_path: Path, state_directory: Path):
    '''Process course and actor state under one checkpoint and exact retry boundary.'''
    state_directory.mkdir(parents=True,exist_ok=True)
    snapshot=state_directory/'navigation.json'
    navigator=Navigator(spec_path)
    state=json.loads(snapshot.read_text()) if snapshot.is_file() else navigator.initial()
    if state['actor']['fingerprint'] != navigator.deployment.fingerprint:
        raise ValueError('The manifest changed for the existing navigation session')
    for line in sys.stdin:
        packet=json.loads(line)
        response,updated=navigator.step(packet,state)
        if updated is not state:
            commit(snapshot,updated)
            state=updated
        print(json.dumps(response,allow_nan=False,separators=(',',':')),flush=True)
