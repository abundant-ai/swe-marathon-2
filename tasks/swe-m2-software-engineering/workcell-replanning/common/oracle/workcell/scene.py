"""Rebuild the authoritative scene before considering robot motion."""

from dataclasses import dataclass
import json

from .model import (Capsule, Object, Robot, array, capsule, frame, identifier, integer, joint, obj,
                    tool_point, world_point)


@dataclass(frozen=True)
class Scene:
    """A scene revision, world obstacles and optional tool-frame attachment."""

    revision: int
    world: dict[str, Capsule]
    load: tuple[str, Capsule] | None

    def encoded(self) -> Object:
        """Return the JSON representation of the snapshot."""
        attachment = None
        if self.load is not None:
            name, shape = self.load
            attachment = {"id": name, "capsule": shape.encoded()}
        return {"revision": self.revision, "objects": {name: shape.encoded() for name, shape in self.world.items()},
                "attached": attachment}


def scene_from(value: object) -> Scene:
    """Validate the public snapshot and preserve its object identities."""
    data = obj(value)
    revision = integer(data["revision"])
    world = {identifier(name): capsule(shape) for name, shape in obj(data["objects"]).items()}
    if revision < 0:
        raise ValueError("negative scene revision")
    if data["attached"] is None:
        return Scene(revision, world, None)
    attachment = obj(data["attached"])
    name = identifier(attachment["id"])
    if name in world:
        raise ValueError("attachment also present in world")
    return Scene(revision, world, (name, capsule(attachment["capsule"])))


def apply_event(robot: Robot, scene: Scene, event: Object) -> Scene:
    """Apply one new event to an independent snapshot."""
    revision = integer(event["revision"])
    if integer(event["base_revision"]) != scene.revision or revision != scene.revision + 1:
        raise ValueError("scene revision gap or conflict")
    world = dict(scene.world)
    load = scene.load
    operation = identifier(event["op"])
    name = identifier(event["id"])
    match operation:
        case "add":
            if name in world or (load is not None and name == load[0]):
                raise ValueError("add identifies a present object")
            world[name] = capsule(event["capsule"])
        case "move":
            if name not in world:
                raise ValueError("move requires a world object")
            world[name] = capsule(event["capsule"])
        case "remove":
            del world[name]
        case "attach" | "detach":
            q = joint(event["q"])
            if not robot.has_joint_position(q):
                raise ValueError("grasp or release outside joint limits")
            _, _, origin, heading = frame(robot, q)
            if operation == "attach":
                if load is not None:
                    raise ValueError("attachment slot occupied")
                shape = world.pop(name)
                load = (name, Capsule(tool_point(shape.a, origin, heading),
                                      tool_point(shape.b, origin, heading), shape.radius))
            else:
                if load is None or load[0] != name:
                    raise ValueError("detach identifies an unheld object")
                shape = load[1]
                world[name] = Capsule(world_point(shape.a, origin, heading),
                                      world_point(shape.b, origin, heading), shape.radius)
                load = None
        case _:
            raise ValueError("unknown object operation")
    return Scene(revision, world, load)


def reconcile(robot: Robot, initial: object, events: object) -> Scene:
    """Reconcile revision order and ignore exact retransmissions."""
    scene = scene_from(initial)
    history = {}
    for item in array(events):
        event = obj(item)
        event_id = identifier(event["event_id"])
        encoded = json.dumps(event, sort_keys=True, allow_nan=False)
        if event_id in history:
            if history[event_id] != encoded:
                raise ValueError("event ID reused with changed contents")
            continue
        scene = apply_event(robot, scene, event)
        history[event_id] = encoded
    return scene
