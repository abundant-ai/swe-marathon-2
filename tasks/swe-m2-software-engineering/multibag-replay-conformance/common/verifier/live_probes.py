"""Verify actual ROS replay publication with independent native subscribers."""

from collections import Counter
from contextlib import contextmanager
from hashlib import sha256
import json
from pathlib import Path
import select
import shutil
import signal
import subprocess
import sys
from time import monotonic
from uuid import uuid4

from geometry_msgs.msg import TransformStamped
import rclpy
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from rclpy.serialization import serialize_message
from rosbags.rosbag2 import StoragePlugin, Writer
from rosbags.typesys import Stores, get_typestore
from std_msgs.msg import String
from tf2_msgs.msg import TFMessage


def tf(child):
    item=TransformStamped()
    item.header.frame_id='map'
    item.child_frame_id=child
    item.transform.rotation.w=1.
    return serialize_message(TFMessage(transforms=[item]))


class Replay:
    """Drive a fresh candidate process through real native I/O and read-only receipts."""

    def __init__(self,run,workspace):
        self.run=run
        self.workspace=workspace
        workspace.mkdir()
        workspace.chmod(0o777)
        self.state=workspace/'state'
        self.process=None

    def split(self,shard,stream,boot,backend,rows):
        topics={topic:kind for _,topic,kind,_ in rows}
        with Writer(self.workspace/shard,version=9,storage_plugin=backend) as writer:
            ts=get_typestore(Stores.ROS2_JAZZY)
            handles={topic:writer.add_connection(topic,kind,typestore=ts) for topic,kind in topics.items()}
            for stamp,topic,_,raw in rows:
                writer.write(handles[topic],stamp,raw)
        return {'id':shard,'path':shard,'stream':stream,'boot':boot,'repeats':[],
                'latched_topics':['/tf_static'] if '/tf_static' in topics else []}

    def attach(self,base,shards,count):
        path=self.workspace/f'attach-{base}.json'
        report=self.workspace/f'report-{base}.json'
        path.write_text(json.dumps({'operation':'attach','request_id':f'attach-{base}',
                                    'base_generation':base,'shards':shards}))
        assert self.run('serve','--request',path,'--state',self.state,'--output',report)==0
        assert json.loads(report.read_text())=={'generation':base+1,'events':count}
        for item in shards:
            shutil.rmtree(self.workspace/item['path'])

    def launch(self):
        flags=[sys.executable,'-B','-m','bag_conformance','live','--state',str(self.state)]
        self.process=subprocess.Popen(flags,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,text=True,cwd=self.run.app,env=self.run.environment(),start_new_session=True,
            **self.run.options())
        return self

    def close(self):
        if self.process is not None:
            try:
                import os
                os.killpg(self.process.pid,signal.SIGKILL)
            except ProcessLookupError:
                pass
            self.process.wait(timeout=4)
            self.process.stdin.close()
            self.process.stdout.close()
            self.process=None

    def __enter__(self):
        return self.launch()

    def __exit__(self,*unused):
        self.close()

    def send(self,packet,unread=False,error=False):
        self.process.stdin.write(json.dumps(packet)+'\n')
        self.process.stdin.flush()
        if unread:
            return None
        assert select.select([self.process.stdout],[],[],8)[0], 'worker response timed out'
        result=json.loads(self.process.stdout.readline())
        assert ('error' in result)==error,result
        return result

    def open(self,name,begin=107,end=160):
        return self.send(dict(operation='open',request_id=f'open-{name}',reader=name,generation=None,
                              topics=['/tf_static','/sensor'],begin_ns=begin,end_ns=end))

    def request(self,reader,size,label):
        return dict(operation='prepare',request_id='prepare-'+label,reader=reader,max_events=size,max_bytes=8192)

    def emit(self,batch,**extra):
        return self.send(dict(operation='emit',reader=batch['reader'],epoch=batch['epoch'],batch=batch['batch'],**extra))

    def ack(self,batch,label):
        return self.send(dict(operation='ack',request_id='ack-'+label,reader=batch['reader'],epoch=batch['epoch'],batch=batch['batch']))

    def observed_commit(self,request_id):
        command=[sys.executable,'-B','-m','bag_conformance','receipt','--state',str(self.state),'--request-id',request_id]
        expires=monotonic()+8
        while monotonic()<expires:
            output=subprocess.check_output(command,stderr=subprocess.DEVNULL,cwd=self.run.app,
                                            env=self.run.environment(),timeout=4,**self.run.options())
            receipt=json.loads(output)
            if receipt is not None:
                return receipt
        raise AssertionError('durable acceptance was never observed')


@contextmanager
def listen(prefix):
    """Start a genuine native DDS reader after earlier publications when needed."""
    node=rclpy.create_node('probe_'+uuid4().hex[:12])
    retained,regular=[],[]
    for name,model,buffer,is_latched in (('/tf_static',TFMessage,retained,True),('/sensor',String,regular,False)):
        qos=QoSProfile(depth=12,reliability=ReliabilityPolicy.RELIABLE,
                       durability=DurabilityPolicy.TRANSIENT_LOCAL if is_latched else DurabilityPolicy.VOLATILE)
        node.create_subscription(model,prefix+name,buffer.append,qos,raw=True)
    try:
        yield node,retained,regular
    finally:
        node.destroy_node()


def collected(observer,expected,ordinary=(),window=1.5):
    node,retained,regular=observer
    until=monotonic()+window
    while monotonic()<until:
        rclpy.spin_once(node,timeout_sec=.035)
    return Counter(retained)==Counter(expected) and Counter(regular)==Counter(ordinary)


def make_seed(replay):
    old,other,fresh=[tf('child_'+uuid4().hex[:8]) for _ in range(3)]
    volatile=serialize_message(String(data='trigger_'+uuid4().hex+'xyz'))
    hidden=serialize_message(String(data='boot_'+uuid4().hex))
    native='tf2_msgs/msg/TFMessage'; string='std_msgs/msg/String'
    primary=replay.split('primary','mapper','old',StoragePlugin.SQLITE3,
        [(100,'/tf_static',native,old),(111,'/sensor',string,volatile)])
    untouched=replay.split('other','lidar','boot',StoragePlugin.MCAP,[(102,'/tf_static',native,other)])
    replay.attach(0,[primary,untouched],3)
    def advance():
        changed=replay.split('new','mapper','new',StoragePlugin.MCAP,
            [(122,'/diag',string,hidden),(144,'/tf_static',native,fresh)])
        replay.attach(1,[changed],5)
    return old,other,fresh,volatile,advance


def epoch_missions(run,root):
    replay=Replay(run,root)
    old,side,fresh,text,advance=make_seed(replay)
    result={}
    with replay:
        earlier=replay.open('old')
        advance()
        latest=replay.open('new')
        original=replay.send(replay.request('old',10,'all-old'))
        with listen(earlier['prefix']) as active:
            live=replay.emit(original,wait_for_subscribers=['/sensor','/tf_static'])
            result['native_cdr_and_compatible_volatile_delivery']=(live['published']==3 and collected(active,[old,side],[text]))
        assert replay.ack(original,'all-old')['acknowledged']
        initial=replay.send(replay.request('new',3,'first-new'))
        replay.emit(initial)
        replay.ack(initial,'first-new')
        with listen(earlier['prefix']) as late:
            result['late_subscribers_receive_each_stream_without_volatile_history']=(earlier['generation']==1 and latest['generation']==2 and collected(late,[old,side]))
        boot=replay.send(replay.request('new',1,'boot-boundary'))
        assert boot['events']==[] and boot['scanned']==1 and replay.emit(boot)['published']==0
        replay.ack(boot,'boot')
        with listen(latest['prefix']) as now:
            current=collected(now,[side])
        with listen(earlier['prefix']) as still_old:
            result['unselected_new_boot_retires_old_writer_only_on_current_generation']=current and collected(still_old,[old,side])
        pending=replay.send(replay.request('new',4,'preseek'))
        sought=replay.send(dict(operation='seek',reader='new',request_id='seek-final',begin_ns=145,end_ns=160))
        assert sought['generation']==2 and sought['epoch']==latest['epoch']+1 and sought['prefix']!=latest['prefix']
        assert 'error' in replay.send(dict(operation='emit',reader='new',epoch=pending['epoch'],batch=pending['batch']),error=True)
        selection=replay.send(replay.request('new',5,'after-seek'))
        replay.emit(selection)
        replay.ack(selection,'after-seek')
        with listen(sought['prefix']) as here, listen(latest['prefix']) as stale:
            result['fresh_seek_fences_pending_batch_and_rebuilds_latches']=collected(here,[side,fresh]) and collected(stale,[])
    return result


def interrupted_acceptance(run,root):
    replay=Replay(run,root)
    old,side,_,text,_=make_seed(replay)
    with replay:
        opened=replay.open('restart')
        first=replay.send(replay.request('restart',2,'retained'))
        with listen(opened['prefix']) as current:
            replay.emit(first,wait_for_subscribers=['/tf_static'])
            assert collected(current,[old,side])
        replay.ack(first,'retained')
        request=replay.request('restart',1,'unread-before-kill')
        replay.send(request,unread=True)
        receipt=replay.observed_commit(request['request_id'])
        assert receipt['events'][0]['sha256']==sha256(text).hexdigest()
        replay.close()
        replay.launch()
        assert replay.send(request)==receipt
        assert replay.send(request|{'max_events':2},error=True).get('error')
        with listen(opened['prefix']) as restored:
            assert collected(restored,[old,side])
            assert replay.emit(receipt,wait_for_subscribers=['/sensor'])['published']==1
            assert collected(restored,[old,side],[text])
        assert replay.ack(receipt,'restored')['acknowledged']
        replay.send(dict(operation='emit',reader='restart',epoch=0,batch=receipt['batch']),error=True)
    return True


def live_checks(run,root):
    outcomes=dict.fromkeys(('native_cdr_and_compatible_volatile_delivery',
                            'late_subscribers_receive_each_stream_without_volatile_history',
                            'unselected_new_boot_retires_old_writer_only_on_current_generation',
                            'fresh_seek_fences_pending_batch_and_rebuilds_latches',
                            'accepted_prepare_survives_real_worker_kill'),False)
    rclpy.init()
    try:
        try:
            outcomes.update(epoch_missions(run,root/'native-live-epoch'))
        except (AssertionError,AttributeError,KeyError,OSError,RuntimeError,ValueError,subprocess.SubprocessError):
            pass
        try:
            outcomes['accepted_prepare_survives_real_worker_kill']=interrupted_acceptance(run,root/'native-live-kill')
        except (AssertionError,AttributeError,KeyError,OSError,RuntimeError,ValueError,subprocess.SubprocessError):
            pass
    finally:
        rclpy.shutdown()
    return outcomes
