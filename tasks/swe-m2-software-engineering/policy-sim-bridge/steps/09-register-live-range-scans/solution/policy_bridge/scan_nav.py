"""Build a planar map from raw range scans, register odom epochs, and walk."""

from collections import deque
from base64 import b64decode, b64encode
from heapq import heappush, heappop
from itertools import product
import json
from math import ceil, hypot
from pathlib import Path
import sys
import zlib

import numpy as np

from .course_planner import heading, pursuit_twist
from .locomotion import Deployment, canonical, commit, integer, vector


def rotate(value, yaw):
    x, y = np.moveaxis(np.asarray(value), -1, 0)
    c, s = np.cos(yaw), np.sin(yaw)
    return np.stack((c*x-s*y, s*x+c*y), axis=-1)


def compose(a, b):
    x, y = np.asarray(a[:2])+rotate(b[:2], a[2])
    return np.array([x,y,heading(a[2]+b[2])])


def inverse(a):
    return np.r_[rotate(-np.asarray(a[:2]),-a[2]),-a[2]]


class Occupancy:
    """Maintain observed free and occupied evidence on a finite surveyed grid."""

    def __init__(self, extent, cell):
        self.site_lower = np.array(extent)[[0,2]]
        self.site_upper = np.array(extent)[[1,3]]
        self.lower = self.site_lower-2*cell
        self.upper = self.site_upper+2*cell
        self.cell = cell
        self.nx,self.ny = np.ceil((self.upper-self.lower)/cell).astype(int)
        self.odds = np.zeros((self.ny,self.nx), dtype=np.int8)

    def membership(self, point):
        index = np.floor((np.asarray(point)-self.lower)/self.cell).astype(int)
        return index, np.all((index >= 0) & (index < [self.nx,self.ny]),axis=-1)

    def centers(self, cells):
        return self.lower+(np.asarray(cells)+.5)*self.cell

    def flats(self, points):
        cells,valid = self.membership(points)
        return np.unique(cells[valid,1]*self.nx + cells[valid,0])

    def record(self, origin, directions, lengths, hits):
        steps = np.arange(0,float(max(lengths))+self.cell/3,self.cell*.51)
        ray_lengths = lengths-np.where(hits,self.cell*.73,0)
        samples = (origin+directions[:,None,:]*steps[None,:,None])[steps[None,:]<=ray_lengths[:,None]]
        free = self.flats(samples)
        occupied = self.flats(origin+directions[hits]*lengths[hits,None])
        free = np.setdiff1d(free,occupied,assume_unique=True)
        flat = self.odds.reshape(-1)
        before = flat>0
        flat[free] = np.maximum(-5,flat[free]-2)
        flat[occupied] = np.minimum(5,flat[occupied]+3)
        return bool(np.any((flat>0)!=before))

    def distance_field(self):
        hits = np.argwhere(self.odds>0)
        if not len(hits):
            raise ValueError('The teaching sequence yielded no surfaces')
        grid = np.indices(self.odds.shape).transpose(1,2,0).reshape(-1,2)
        output = []
        for n in range(0,len(grid),256):
            delta = grid[n:n+256,None,:]-hits[None,:,:]
            output.extend(np.sqrt((delta**2).sum(axis=-1).min(axis=1))*self.cell)
        return np.minimum(.26,np.asarray(output)).reshape(self.odds.shape)

    def field_cost(self, field, query):
        points = (query-self.lower)/self.cell-.5
        index = np.floor(points).astype(int)
        valid = np.all((index>=0)&(index<[self.nx-1,self.ny-1]),axis=-1)
        dx, dy = np.moveaxis(points-index,-1,0)
        x, y = np.moveaxis(np.clip(index,0,[self.nx-2,self.ny-2]),-1,0)
        result = (1-dy)*((1-dx)*field[y,x]+dx*field[y,x+1])+dy*((1-dx)*field[y+1,x]+dx*field[y+1,x+1])
        return np.where(valid,result,.26)

    def obstacles(self, clearance):
        occupied = self.odds>0
        blocked = occupied.copy()
        pad = ceil(clearance/self.cell)
        for dy, dx in product(range(-pad,pad+1),repeat=2):
            if hypot(dx,dy)*self.cell>clearance:
                continue
            dest_x = slice(max(0,dx),self.nx+min(0,dx))
            dest_y = slice(max(0,dy),self.ny+min(0,dy))
            src_x = slice(max(0,-dx),self.nx+min(0,-dx))
            src_y = slice(max(0,-dy),self.ny+min(0,-dy))
            blocked[dest_y,dest_x] |= occupied[src_y,src_x]
        coordinates = np.indices(self.odds.shape).transpose(1,2,0)[:,:,::-1]
        centers = self.centers(coordinates)
        blocked |= np.any((centers < self.site_lower+clearance)|(centers > self.site_upper-clearance),axis=-1)
        return blocked


class Planner:
    """Search free cells using footprint-inflated sensor evidence."""

    def __init__(self, occupancy, clearance):
        self.grid = occupancy
        self.blocked = occupancy.obstacles(clearance)
        self.unknown = occupancy.odds==0

    def visible(self,a,b):
        steps = max(2,ceil(np.linalg.norm(np.asarray(b)-a)/(self.grid.cell*.42)))
        segment = np.linspace(a,b,steps,endpoint=True)
        cells,inside = self.grid.membership(segment)
        return bool(np.all(inside) and not np.any(self.blocked[cells[:,1],cells[:,0]]))

    def path(self,start,destination):
        if self.visible(start,destination):
            return [np.asarray(destination)]
        start_cell,inside = self.grid.membership(start)
        end_cell,finish = self.grid.membership(destination)
        if not (inside and finish):
            return []
        first,target = tuple(start_cell),tuple(end_cell)
        if self.blocked[first[1],first[0]] or self.blocked[target[1],target[0]]:
            return []
        parents,costs = {first:None},{first:0.}
        frontier = [(0.,0.,first)]
        while frontier:
            _,cost,base = heappop(frontier)
            if costs[base]!=cost:
                continue
            if base==target:
                result = [np.asarray(destination)]
                while base is not None:
                    result.append(self.grid.centers(base))
                    base=parents[base]
                return result[::-1]
            x,y = base
            for dx,dy in ((1,0),(0,1),(-1,0),(0,-1),(1,1),(-1,1),(1,-1),(-1,-1)):
                nx,ny = x+dx,y+dy
                if (not 0<=nx<self.grid.nx or not 0<=ny<self.grid.ny or self.blocked[ny,nx]
                        or (dx and dy and (self.blocked[y,nx] or self.blocked[ny,x]))):
                    continue
                next_cost = cost+hypot(dx,dy)*(1.45 if self.unknown[ny,nx] else 1.)
                point=nx,ny
                if next_cost>=costs.get(point,float('inf')):
                    continue
                costs[point],parents[point]=next_cost,base
                heappush(frontier,(next_cost+hypot(target[0]-nx,target[1]-ny),next_cost,point))
        return []

    def pursuit(self,position,path):
        if not path:
            return None
        nearest = min(range(len(path)),key=lambda idx:np.linalg.norm(path[idx]-position))
        return next((point for point in path[max(0,nearest-1):][::-1] if self.visible(position,point)),None)


class ScanNavigation:
    """Resolve the global map from calibrated scans without surveyed live poses."""

    def __init__(self, manifest):
        spec = json.loads(manifest.read_text())
        self.site = spec['scan_navigation']
        self.actor = Deployment(manifest)
        self.control = self.actor.initial()
        self.scan_mount = np.asarray(self.site['body_from_lidar'])
        self.beam_angles = (self.site['angle_min_rad'] +
                            np.arange(self.site['beam_count'])*self.site['angle_step_rad'])
        self.beam = np.c_[np.cos(self.beam_angles),np.sin(self.beam_angles)]
        self.limit = self.site['range_max_m']
        self.grid = Occupancy(self.site['extent'],self.site['resolution_m'])
        self.map_origin = np.asarray(self.site['teach_anchor'])
        cursor = self.map_origin
        for record in spec['teaching']:
            cursor = compose(cursor,record['delta'])
            self.integrate(cursor,record['ranges_m'])
        self.surface = self.grid.distance_field()
        self.planning = Planner(self.grid,self.site['footprint_radius_m']+.065)
        self.recovery = Planner(self.grid,self.site['footprint_radius_m']+.012)
        self.goal = np.asarray(self.site['goal'])
        self.offset = None
        self.map_hint = self.map_origin
        self.odom = np.zeros(3)
        self.velocity_local = np.zeros(2)
        self.last_scan = None
        self.epoch = None
        self.poses = deque(maxlen=self.site['max_scan_age_ticks']+2)
        self.path = []
        self.pose = None

    def decode(self,ranges):
        if not isinstance(ranges,list) or len(ranges)!=len(self.beam):
            raise ValueError('Range vector does not match the calibrated beam layout')
        if any(value is not None and type(value) not in (float,int) for value in ranges):
            raise ValueError('Each beam is a length or null')
        lengths = np.array([self.limit if r is None else r for r in ranges],dtype=float)
        hits = np.array([value is not None for value in ranges])
        if not np.all(np.isfinite(lengths)) or np.any(lengths<=0) or np.any(lengths>self.limit):
            raise ValueError('Nonfinite or out-of-range beam')
        return lengths,hits

    def integrate(self,map_pose,ranges):
        origin = compose(map_pose,self.scan_mount)
        lengths,hits = self.decode(ranges)
        return self.grid.record(origin[:2],rotate(self.beam,origin[2]),lengths,hits)

    def fit(self,guess,ranges,lost):
        lengths,hits = self.decode(ranges)
        endpoint = rotate(self.beam[hits]*lengths[hits,None],self.scan_mount[2])+self.scan_mount[:2]
        if len(endpoint)<30:
            return None,None
        endpoint = endpoint[::2]

        def search(center, spatial, angular, step):
            if step:
                number = round(spatial/step)
                space = np.arange(-number,number+1)*step
                angle = np.linspace(-angular,angular,2*number+1)
            else:
                space,angle = np.array([-spatial,0.,spatial]),np.array([-angular,0.,angular])
            trial = center + np.array(list(product(space,space,angle)))
            query = rotate(endpoint[None,:,:],trial[:,None,2])+trial[:,None,:2]
            field = self.grid.field_cost(self.surface,query)
            metric = np.minimum(field,.19)**2
            cost = metric.mean(axis=1)
            valid = np.all((trial[:,:2]>=self.grid.site_lower+.30)&(trial[:,:2]<=self.grid.site_upper-.30),axis=1)
            prior = .00007*np.sum((trial-guess)**2,axis=1) if not lost else 0.
            best = np.argmin(cost + prior + np.where(valid,0.,1.))
            return trial[best], float(np.sqrt(cost[best]))

        if lost:
            selected,quality = search(guess,.85,.90,.17)
            for spatial,angular in ((.10,.11),(.045,.052),(.019,.025),(.009,.011)):
                selected,quality = search(selected,spatial,angular,0.)
        else:
            selected,quality = search(guess,.112,.070,.056)
            for spatial,angular in ((.028,.034),(.013,.018),(.006,.008)):
                selected,quality = search(selected,spatial,angular,0.)
        if quality >= (.105 if lost else .12):
            return None,quality
        selected[2] = heading(selected[2])
        return selected,quality

    def update(self,tick, odometry, ranges):
        epoch = integer(odometry['epoch'],'odometry epoch')
        delta = np.asarray(vector(odometry['delta'],3,'body odometry step'))
        if (self.epoch is None or epoch>self.epoch) and np.any(delta):
            raise ValueError('A new epoch starts at its own origin')
        if self.epoch is None:
            self.epoch = epoch
            self.offset = self.map_origin
        elif epoch > self.epoch:
            self.epoch = epoch
            self.offset = None
            self.last_scan = None
            self.odom = np.zeros(3)
            self.poses.clear()
            self.path = []
        if epoch != self.epoch:
            raise ValueError('Stale odometry epoch')
        self.velocity_local = .72*self.velocity_local+.28*rotate(delta[:2],self.odom[2])/.02
        self.odom = compose(self.odom,delta)
        self.poses.append((tick,self.odom.copy()))
        historic = dict(self.poses)
        updated_geometry = False
        for scan in sorted(ranges, key=lambda row:row['capture_tick']):
            stamp = scan['capture_tick']
            if (scan['epoch']!=self.epoch or stamp not in historic or tick-stamp>self.site['max_scan_age_ticks']
                    or self.last_scan is not None and stamp<=self.last_scan):
                continue
            lost = self.offset is None
            guess = self.map_hint if lost else compose(self.offset,historic[stamp])
            fitted, _ = self.fit(guess,scan['ranges_m'],lost)
            if fitted is None:
                continue
            self.offset = compose(fitted,inverse(historic[stamp]))
            self.last_scan = stamp
            updated_geometry |= self.integrate(fitted,scan['ranges_m'])
        if updated_geometry:
            self.planning = Planner(self.grid,self.site['footprint_radius_m']+.065)
            self.recovery = Planner(self.grid,self.site['footprint_radius_m']+.012)
        if self.offset is not None:
            self.pose = compose(self.offset,self.odom)
            if self.last_scan is not None and tick-self.last_scan<=self.site['max_scan_age_ticks']:
                self.map_hint = self.pose
        else:
            self.pose = None
        return updated_geometry

    def move(self,tick,changed):
        stop = 'hold',[0.,0.,0.]
        if (self.pose is None or self.last_scan is None
                or tick-self.last_scan>self.site['max_scan_age_ticks']):
            return stop
        position,angle = self.pose[:2],self.pose[2]
        distance = np.linalg.norm(position-self.goal[:2])
        velocity = rotate(self.velocity_local,self.offset[2])
        if distance < .101 and abs(heading(angle-self.goal[2]))<.110:
            return 'arrived',[0.,0.,0.]
        if not self.planning.visible(position,position):
            index, _ = self.grid.membership(position)
            points = self.grid.centers(index+np.array(list(product(range(-5,6),repeat=2))))
            reachable = [p for p in points if self.planning.visible(p,p) and self.recovery.visible(position,p)]
            if not reachable:
                return stop
            waypoint = min(reachable,key=lambda p:np.linalg.norm(p-position))
            self.path = []
            return 'navigate',pursuit_twist(position,velocity,angle,waypoint,0.,.21)
        if changed or not self.path or tick%15==0:
            self.path = self.planning.path(position,self.goal[:2])
        point = self.planning.pursuit(position,self.path)
        if point is None:
            self.path = self.planning.path(position,self.goal[:2])
            point = self.planning.pursuit(position,self.path)
            if point is None:
                return stop
        desired_yaw = self.goal[2] if distance<.85 else 0.
        twist = pursuit_twist(position,velocity,angle,point,desired_yaw,self.site['max_speed_mps'])
        return 'navigate',twist

    def step(self,packet):
        tick = packet['tick']
        changed = self.update(tick,packet['odometry'],packet['scans'])
        mode,twist = self.move(tick,changed)
        lease = {'sequence':tick,'valid_until_tick':tick+1,'velocity':twist}
        result,self.control = self.actor.step({**packet,'request':lease},self.control)
        return {**result,'navigation':mode,'intent':lease,'localization_epoch':self.epoch,
                'accepted_scan_tick':self.last_scan,'pose_map':self.pose.tolist() if self.pose is not None else None}

    def snapshot(self, request, response):
        """Save the actor, map, history and receipt in the same transaction."""
        return {
            'control':self.control,
            'grid':b64encode(zlib.compress(self.grid.odds.tobytes())).decode('ascii'),
            'offset':self.offset.tolist() if self.offset is not None else None,
            'map_hint':self.map_hint.tolist(),
            'odom':self.odom.tolist(),
            'velocity_local':self.velocity_local.tolist(),
            'last_scan':self.last_scan,
            'epoch':self.epoch,
            'poses':[[tick, pose.tolist()] for tick,pose in self.poses],
            'path':[point.tolist() for point in self.path],
            'request':request,
            'response':response,
        }

    def recover(self,state):
        """Reinstate only the committed evidence, retaining the immutable teaching map."""
        if state['control']['fingerprint'] != self.actor.fingerprint:
            raise ValueError('The manifest changed for the existing scan-navigation session')
        self.control = state['control']
        self.grid.odds[:] = np.frombuffer(zlib.decompress(b64decode(state['grid'])),dtype=np.int8).reshape(
            self.grid.odds.shape)
        self.offset = np.asarray(state['offset']) if state['offset'] is not None else None
        self.map_hint = np.asarray(state['map_hint'])
        self.odom = np.asarray(state['odom'])
        self.velocity_local = np.asarray(state['velocity_local'])
        self.last_scan,self.epoch = state['last_scan'],state['epoch']
        self.poses.extend((tick,np.asarray(pose)) for tick,pose in state['poses'])
        self.path = [np.asarray(point) for point in state['path']]
        self.planning = Planner(self.grid,self.site['footprint_radius_m']+.065)
        self.recovery = Planner(self.grid,self.site['footprint_radius_m']+.012)


def navigate_scans(manifest: Path, state_directory: Path):
    """Serve one observation at a time, preserving exact replies across worker death."""
    state_directory.mkdir(parents=True,exist_ok=True)
    path = state_directory/'scan-navigation.json'
    navigator = ScanNavigation(manifest)
    state = None
    if path.is_file():
        state = json.loads(path.read_text())
        navigator.recover(state)
    for line in sys.stdin:
        packet = json.loads(line)
        tick = integer(packet['tick'],'tick')
        previous = navigator.control['tick']
        request = canonical(packet)
        if tick == previous and state and request == state['request']:
            result = state['response']
        elif tick != previous+1:
            result = {'tick':tick,'mode':'rejected','lease':None,'support':[],
                      'effective_twist':None,'action':None,'target_rad':None}
        else:
            result = navigator.step(packet)
            state = navigator.snapshot(request,result)
            commit(path,state)
        print(canonical(result),flush=True)
