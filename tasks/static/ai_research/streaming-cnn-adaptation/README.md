# Train and adapt a CNN from live CORe50 images

The version 2 scanner task trains a source classifier and commissions two stockrooms whose local identifiers disagree. The submitted updater receives unlabelled RGB frames, reads visual handovers and edits the classifier after each prediction. It must classify inventory at both sites and preserve headquarters recognition. The hosted package is a static task.

Run the following from this directory using the pinned CPU environment in environment/Dockerfile and the original CORe50 32 × 32 RGB archive. The command creates the three self-contained Harbor task directories and audits their image pairing. The output directory must be new.

```sh
python site_handover/build.py /path/to/core50_32x32.zip /tmp/core50-scanner-tasks
```

The matched version 2 reference earned 1.0. All nine matched model submissions earned zero. Only three completed the numerical replay. [Model and control trials](https://www.oddish.app/experiments/560dfbfe) · [Native results](site_handover/three-model-v2.json) · [Task and review history](site_handover/README.md) · [CORe50 source and attribution](public/CORe50-attribution.txt)
