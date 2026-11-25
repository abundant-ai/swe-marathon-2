# Fixed-lag fusion inputs

GTSAM 4.3.0 is preinstalled for factor-graph experimentation. The CLI can use any installed implementation that satisfies the contract. GTSAM's Plaza2 example demonstrates the real wheel and radio-ranging workflow. https://gtbook.github.io/gtsam-examples/RangeISAMExample_plaza2.html

`room1_xy.csv` contains 80 planar positions from the room1 TUM VI motion-capture stream at approximately 75 ms intervals. It retains the times as represented in the source CSV, drops height and orientation, and takes every ninth record from a portion of the room sequence. The tracked rig is handheld. The file describes its motion and can be used to generate commissioning exercises for planar fusion.

The TUM VI dataset is by David Schubert, Thore Goll, Nikolaus Demmel, Vladyslav Usenko, Jörg Stückler and Daniel Cremers. Original data is licensed CC BY 4.0. The source was the room1 ground-truth CSV extracted by the public IMU-only mirror. The full mirror input SHA-256 is `959bd51462d7f3ef6b1bac712ece7e6d6ab46f73679b22d8801aa38e1ed51a36`.

- [TUM VI dataset and license](https://cvg.cit.tum.de/data/datasets/visual-inertial-dataset#license)
- [TUM VI benchmark paper](https://arxiv.org/abs/1804.06120)
- [Source CSV used for the excerpt](https://github.com/BahMoh/TUMVI-IMU-only-Dataset-room1-to-room6/blob/master/dataset-room1_512_16_gt.csv)

For the visual graph checkpoint, run
`python3 /app/examples/native_track_example.py /tmp/track-manifest.json > /tmp/tracks.ndjson`.
The manifest and stream show two frames sharing a surveyed point.
Pass those records to `smooth-tracks --manifest /tmp/track-manifest.json`.
