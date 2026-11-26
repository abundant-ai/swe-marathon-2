# Merrow Bay: the game project

This is the Godot 4.7.2 project for Merrow Bay (a working name). The design document and the
world plans are in `/app/design` (`GDD.md`, `plan/`). Our QA kit and its playtests are in
`/app/qa-kit`.

## What is here

- `project.godot`: the engine settings chapter 16 of the design document fixes (Jolt Physics,
  60 physics ticks per second, `physics_jitter_fix` 0, physics on the main thread, the
  Compatibility renderer) and the 28 input actions of chapter 4, each with keyboard or mouse
  and gamepad bindings.
- `dev_console.gd`: the `DevConsole` autoload of chapter 17. For now every command answers
  `{"ok": false, "error": "not implemented"}`.
- `main.tscn`: an empty main scene.
- `assets/vendor/`: the art library, all CC0 (licences in each folder):
  - `kenney_car_kit/`, `kenney_city_roads/`: Kenney's car kit and road kit;
  - `ubc/`, `ubc_hair/`: Quaternius' two base bodies, their hair and eyebrows;
  - `ual/`: Quaternius' animation library (`UAL1_Standard.glb` in place,
    `UAL1_Standard_RM.glb` with root motion).

## The art library

Every asset's `.import` file sets its import options explicitly. Textures are VRAM-compressed
with mipmaps and never wait for the editor's "detect 3D" step, which headless imports skip.
`humanoid_bone_map.tres` maps the library's bone names to Godot's humanoid profile, and the
bodies, the hair and both animation files import through it. So the body scenes come with a
`Skeleton3D` that uses the profile's bone names (design document, AC-5), and the clips target
the same names. Keep these files, or replace them with your own.

Release builds take the vendor library as we ship it: only the `.import` and `.tres` files under
`assets/vendor/` carry over from your project. Put the meshes, materials and scenes you make under
`assets/` outside `vendor/`.

The body glTF files name two textures the pack does not include (`T_Eye_Normal_png.png`,
`T_Hair_1_Normal_png.png`). The import reports them and carries on.

## Running it

    godot --path /app/game -- --role=solo
    godot --headless --path /app/game -- --role=server --port=47000

Chapter 17 lists every flag. Run QA's playtests with `qa run` (see `/app/qa-kit/README.md`).
