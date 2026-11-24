# Commission two six-axis arms in the surveyed cell

The next cell uses two UR5e arms. The nominal robot models are available, but each mount and marker has a different rigid offset. Recover both offsets from the commissioning captures and check them against independent measurements. Keep the earlier commands available.

```bash
python3 -m dual_arm commission-native --spec SPEC.json --output REPORT.json
```

`robot_xml` contains the supplied single-arm collision-only UR5e model. The same public model is available as `/app/examples/ur5e-headless.xml`. MuJoCo 3.3.7 and NumPy are installed. Use the six hinge coordinates in model order and the `attachment_site` as the flange frame. The model reference is the native model world, including the asset's own base orientation.

`captures` maps `left` and `right` to `fit` and `validation` arrays. Each row contains `q` (six radian hinge coordinates) and a measured `marker` pose in the surveyed world frame. A pose has `translation_m` (three coordinates) and `quaternion_xyzw` (four components with nonzero norm). Use rigid transforms that map local coordinates into the named parent frame. Fit the rigid `world_from_base` and `flange_from_marker` such that

```text
world_from_marker = world_from_base * native_from_flange(q) * flange_from_marker
```

Use only fit data to estimate these transforms. Fewer than 20% of a supported fit capture may contain gross errors. A fit inlier has Euclidean translation error at most `fit_threshold_m` and shortest rotation error at most `fit_threshold_rad`. Require `min_inliers` (an integer at least six) and observable rotation about at least two independent axes. Finite thresholds are positive. Validation has at least one sample per arm. Report `unidentifiable` if either arm lacks support. Do not use held-out poses to identify or revise a fitted transform.

Return `status`, `calibration`, and `validation`. Each arm's `calibration` entry has `world_from_base`, `flange_from_marker`, and `inliers`. Each arm's `validation` entry has `translation_rmse_m` and `rotation_rmse_rad` over the complete held-out array. An error above `validation_threshold_m` or `validation_threshold_rad` for either arm gives `validation_failed` and retains the estimates and metrics. Otherwise return `ok`. For `unidentifiable`, `calibration` and `validation` are null. A malformed request fails with a nonzero exit and preserves the previous output. Keep the numerical fit and input/output logic modular.
