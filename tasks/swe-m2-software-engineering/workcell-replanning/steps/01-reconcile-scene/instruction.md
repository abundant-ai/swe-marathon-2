# Reconcile workcell scene updates

I need a replay tool for our manipulation workcell. We record changes to fixtures and objects as well as the joint reading at each grasp and release. Reconstructing the scene from those messages should tell us which objects are fixed in the cell and which move with the arm. The first version can use our simplified planar cell model.

Write a modular Python 3.12 package under `/app/workcell` that runs offline.

```bash
python3 -m workcell scene --spec SPEC.json --output SCENE.json
```

## Model and input

The spec has `robot`, `initial_scene`, and `events`. Lengths are in metres and angles are in radians. `robot` has the following arrays.

- `lengths_m` and `radii_m` have two positive numbers each, for the upper arm and forearm.
- `joint_limits` has three increasing `[minimum,maximum]` pairs.
- `max_speeds` has three positive numbers, in metres or radians per second. Scene replay uses the joint position limits.

A joint reading `q=[x,shoulder,elbow]` places the base at `[x,0]`. The upper arm has heading `shoulder`. The forearm has heading `shoulder+elbow`. The tool frame origin is the far end of the forearm and its axes have the same heading as the forearm. Joint bounds are inclusive.

A capsule is `{"a":[x,y],"b":[x,y],"radius_m":positive_number}` and consists of all points within the radius of the closed line segment from `a` to `b`. Endpoints may coincide. A scene has `revision` (a nonnegative integer), `objects` (a JSON object mapping nonempty IDs to world-frame capsules), and `attached` (null or `{"id":id,"capsule":capsule}` in tool-frame coordinates). An attached ID must be absent from `objects`. At most one object is carried.

## Replaying and writing the scene

Apply `events` in array order. Each has a nonempty string `event_id`, integer `base_revision` and `revision`, a string `op`, and object `id`. An event must build on the current revision and increment it by exactly one. A repeated event with identical contents is a retransmission even when newer updates have already been applied. Ignore it. A changed event reusing an ID is an error.

- `add` takes a world-frame `capsule` and adds an absent ID.
- `move` takes a world-frame `capsule` and replaces an existing world object.
- `remove` deletes an existing world object.
- `attach` takes a joint reading `q`. Move an existing world object to the empty attachment slot, expressing both endpoints in the tool frame at that reading so the grasp causes no discontinuity.
- `detach` takes a joint reading `q`. Release the matching attached object into the world at its pose at that reading and clear the attachment slot.

Write the reconstructed scene using the same scene format. Reject malformed fields, invalid operations and inconsistent revisions with a nonzero exit code. Leave any existing output unchanged on error. Inputs contain finite numeric fields, with booleans excluded. Unknown metadata keys may be ignored, but they are part of the contents of a retransmitted event.
