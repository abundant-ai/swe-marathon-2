"""Set public process limits before loading the numerical scene builder."""

import importlib
import json
import os
import resource
import sys
from pathlib import Path

if __name__ == "__main__":
    for name, soft, hard in (
        (resource.RLIMIT_CPU, 600, 610),
        (resource.RLIMIT_AS, 3 * 1024**3, 3 * 1024**3),
        (resource.RLIMIT_FSIZE, 64 * 1024**2, 64 * 1024**2),
        (resource.RLIMIT_NOFILE, 128, 128),
        (resource.RLIMIT_NPROC, 32, 32),
        (resource.RLIMIT_CORE, 0, 0),
    ):
        resource.setrlimit(name, (soft, hard))
    np = importlib.import_module("numpy")
    artifact = os.environ.pop("MESH_ARTIFACT")
    fields = json.loads(os.environ.pop("MESH_FIELDS"))
    sys.path.insert(0, str(Path.cwd()))
    fd = int(os.environ.pop("MESH_READY"))
    os.write(fd, b"R")
    os.close(fd)
    submission = importlib.import_module("submission")
    values = submission.scene()
    if not isinstance(values, (tuple, list)) or len(values) != len(fields):
        raise ValueError("Expected the documented scene arrays")
    np.savez(artifact, **dict(zip(fields, values)))
