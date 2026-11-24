"""Independent planar drive, charger contactor, and current telemetry for Jazzy."""

import json
import math
from time import monotonic

from action_msgs.msg import GoalStatusArray
from geometry_msgs.msg import TransformStamped, Twist
from sensor_msgs.msg import BatteryState
from std_msgs.msg import Bool, String, UInt64
from tf2_msgs.msg import TFMessage


SAFE_CURRENT_A = 0.10
CHARGING_CURRENT_A = 1.45
CONTACT_BREAK_X = -0.017
WATCHDOG_S = 0.095


class ReleasePlant:
    """Integrate only applied twists, independent of the electrical reports sent over DDS."""

    def __init__(self, node, power_delay=.68, decay_time=.12, start_x=-.36,
                 frame=(0., 0., 0.), stuck=False):
        if power_delay <= 0 or decay_time <= 0:
            raise ValueError("contactor and current decay times must be positive")
        self.node = node
        self.frame = frame
        self.stuck = stuck
        self.power_delay = power_delay
        self.decay_time = decay_time
        self.pose = [float(start_x), 0.0, 0.0]
        self.started = self.clock = monotonic()
        self.command = (0.0, 0.0, self.clock - 1)
        self.latest_nav = (0.0, 0.0, self.clock - 1)
        self.boot = 173
        self.seq = 0
        self.seated_at = self.clock if self.contact_closed else None
        self.current = 0.0
        self.contactor_open = False
        self.transaction_id = None
        self.request_at = None
        self.physical_open_at = None
        self.current_low_at = None
        self.first_break_at = None
        self.live_breaks = []
        self.requests = []
        self.trace = []
        self.raw_traffic = 0
        self.native_stream = []
        self.actuation_stream = []
        self.native_goals = {}
        self.stale_zero_reports = 0
        self.retired_zero_reports = 0
        self.unsafe_commands = 0
        self.actuator_faults = 0
        self.confirmed = 0
        self.tf = node.create_publisher(TFMessage, "/tf", 20)
        self.powers = node.create_publisher(String, "/departure/power", 30)
        self.qualified = node.create_publisher(BatteryState, "/qualified_battery", 15)
        self.battery = node.create_publisher(BatteryState, "/charger/battery_state", 15)
        self.contact = node.create_publisher(Bool, "/charger/contact", 10)
        self.boot_topic = node.create_publisher(UInt64, "/charger/boot", 10)
        node.create_subscription(Twist, "/cmd_vel", self.receive, 30)
        node.create_subscription(Twist, "/nav2_cmd_vel", self.observe_native, 30)
        node.create_subscription(String, "/departure/isolate", self.isolate, 15)
        for action in ("dock_robot", "undock_robot"):
            node.create_subscription(
                GoalStatusArray, f"/{action}/_action/status",
                lambda message, name=action: self.observe_goal(name, message), 20,
            )
        self.timer = node.create_timer(.015, self.step)

    @property
    def contact_closed(self):
        x, y, yaw = self.pose
        return x >= CONTACT_BREAK_X and abs(y) <= .014 and abs(yaw) <= .16

    @property
    def charged(self):
        return self.contact_closed and self.current > .5

    def reboot(self):
        """Reset the contactor and require a new request in a new charger boot."""
        self.boot += 1
        self.transaction_id = None
        self.request_at = self.physical_open_at = self.current_low_at = None
        self.contactor_open = False

    def _send_power(self, packet):
        self.powers.publish(String(data=json.dumps(packet, separators=(",", ":"))))

    def isolate(self, message, info):
        try:
            packet = json.loads(message.data)
            boot, transaction = packet["boot"], packet["transaction_id"]
            if type(boot) is not int or not isinstance(transaction, str) or not transaction:
                return
        except (KeyError, TypeError, ValueError):
            return
        now = monotonic()
        accepted = boot == self.boot and self.transaction_id in (None, transaction)
        self.requests.append({"time": now, "source_stamp_ns": info["source_timestamp"],
                              "boot": boot, "transaction_id": transaction, "accepted": accepted})
        if accepted and self.transaction_id is None:
            self.transaction_id, self.request_at = transaction, now
        self._send_power({"kind": "ack", "boot": self.boot, "transaction_id": transaction,
                          "stamp_ns": self.node.get_clock().now().nanoseconds,
                          "accepted": accepted})

    def observe_goal(self, action, message):
        for item in message.status_list:
            identity = bytes(item.goal_info.goal_id.uuid).hex()
            key = f"{action}/{identity}"
            statuses = self.native_goals.setdefault(key, [])
            if not statuses or statuses[-1] != item.status:
                statuses.append(item.status)

    def observe_native(self, message):
        v, w = message.linear.x, message.angular.z
        self.latest_nav = (v, w, monotonic())
        if abs(v) > .001 or abs(w) > .001:
            self.raw_traffic += 1
            self.native_stream.append(self.latest_nav)

    def receive(self, message):
        v, w = message.linear.x, message.angular.z
        now = monotonic()
        if not math.isfinite(v) or not math.isfinite(w) or abs(v) > .185 or abs(w) > .505:
            self.actuator_faults += 1
            v = w = 0.0
        if abs(v) > .001 or abs(w) > .001:
            self.actuation_stream.append((v, w, now))
            if (self.contact_closed and self.current > SAFE_CURRENT_A
                    and (v < -.001 or abs(w) > .001)):
                self.unsafe_commands += 1
        self.command = (v, w, now)

    def _physical_current(self, now, contact):
        if not contact:
            return 0.0
        if self.physical_open_at is not None:
            elapsed = max(0.0, now - self.physical_open_at)
            return CHARGING_CURRENT_A * math.exp(-elapsed / self.decay_time)
        if self.seated_at is not None and now - self.seated_at >= .10:
            return CHARGING_CURRENT_A
        return 0.0

    def _integrate(self, now):
        dt, self.clock = min(.04, now - self.clock), now
        x, y, yaw = self.pose
        v, w, stamp = self.command
        if now - stamp > WATCHDOG_S:
            v = w = 0.0
        was_contact = self.contact_closed
        mid_yaw = yaw + .5 * dt * w
        self.pose = [min(.001, x + dt * v * math.cos(mid_yaw)),
                     y + dt * v * math.sin(mid_yaw), yaw + dt * w]
        contact = self.contact_closed
        if was_contact and not contact:
            origin = (x, y, yaw)
            bounds = ((CONTACT_BREAK_X, math.inf), (-.014, .014), (-.16, .16))
            exits = []
            for beginning, end, (lower, upper) in zip(origin, self.pose, bounds, strict=True):
                if end < lower:
                    exits.append((lower - beginning) / (end - beginning))
                elif end > upper:
                    exits.append((upper - beginning) / (end - beginning))
            fraction = min(exits)
            break_at = now - dt * (1 - fraction)
            break_pose = [first + fraction * (last - first)
                          for first, last in zip(origin, self.pose, strict=True)]
            self.first_break_at = self.first_break_at or break_at
            break_current = self._physical_current(break_at, True)
            if break_current > SAFE_CURRENT_A:
                self.live_breaks.append({"time": break_at, "current_amps": break_current,
                                         "pose": break_pose, "boot": self.boot})
        self.seated_at = (self.seated_at or now) if contact else None
        return v, w

    def world(self, pose):
        x, y, yaw = pose
        ox, oy, heading = self.frame
        return [ox + math.cos(heading)*x - math.sin(heading)*y,
                oy + math.sin(heading)*x + math.cos(heading)*y,
                math.remainder(heading + yaw, 2 * math.pi)]

    def _publish_tf(self, stamp):
        x, y, yaw = self.world(self.pose)
        transform = TransformStamped()
        transform.header.stamp = stamp.to_msg()
        transform.header.frame_id = "odom"
        transform.child_frame_id = "base_link"
        transform.transform.translation.x = x
        transform.transform.translation.y = y
        transform.transform.rotation.z = math.sin(yaw / 2)
        transform.transform.rotation.w = math.cos(yaw / 2)
        self.tf.publish(TFMessage(transforms=[transform]))

    def _publish_electrical(self, stamp, contact):
        sample = BatteryState()
        sample.header.stamp = stamp.to_msg()
        sample.header.frame_id = f"charger_boot_{self.boot}"
        sample.current, sample.voltage, sample.present = self.current, 24.6, True
        sample.power_supply_status = (
            BatteryState.POWER_SUPPLY_STATUS_CHARGING if self.current > .5
            else BatteryState.POWER_SUPPLY_STATUS_NOT_CHARGING
        )
        self.qualified.publish(sample)
        self.battery.publish(sample)
        self.contact.publish(Bool(data=contact))
        self.boot_topic.publish(UInt64(data=self.boot))
        self.seq += 1
        report = {"kind": "state", "transaction_id": self.transaction_id, "boot": self.boot,
                  "stamp_ns": stamp.nanoseconds, "seq": self.seq,
                  "current_amps": self.current, "contactor_open": self.contactor_open,
                  "contact": contact}
        if self.transaction_id is not None and contact and self.current > SAFE_CURRENT_A:
            false_open = {**report, "current_amps": 0.0, "contactor_open": True}
            self._send_power({**false_open, "stamp_ns": stamp.nanoseconds - 30_000_000_000})
            self._send_power({**false_open, "boot": self.boot - 1})
            self.stale_zero_reports += 1
            self.retired_zero_reports += 1
        self._send_power(report)

    def step(self):
        now = monotonic()
        if (not self.stuck and self.request_at is not None and self.physical_open_at is None
                and now >= self.request_at + self.power_delay):
            self.contactor_open = True
            self.physical_open_at = self.request_at + self.power_delay
        v, w = self._integrate(now)
        contact = self.contact_closed
        self.current = self._physical_current(now, contact)
        if self.contactor_open and contact and self.current <= SAFE_CURRENT_A:
            self.current_low_at = self.current_low_at or now
        if self.charged:
            self.confirmed += 1
        stamp = self.node.get_clock().now()
        self._publish_tf(stamp)
        self._publish_electrical(stamp, contact)
        self.trace.append({"time": now, "pose": self.pose[:], "v": v, "omega": w, "contact": contact,
                           "current_amps": self.current, "contactor_open": self.contactor_open,
                           "boot": self.boot, "native": self.latest_nav[:2],
                           "transaction_id": self.transaction_id})

    def evidence(self):
        return {"pose": self.pose[:], "requests": self.requests, "isolation_requested_at": self.request_at,
                "physical_open_at": self.physical_open_at, "current_low_at": self.current_low_at,
                "first_break_at": self.first_break_at, "live_breaks": self.live_breaks,
                "stale_zero_reports": self.stale_zero_reports, "retired_zero_reports": self.retired_zero_reports,
                "unsafe_commands": self.unsafe_commands, "actuator_faults": self.actuator_faults,
                "native_commands": self.raw_traffic, "actuated_commands": len(self.actuation_stream),
                "native_goals": self.native_goals}
