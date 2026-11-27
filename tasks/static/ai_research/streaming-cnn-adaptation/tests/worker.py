"""Load the submitted updater in the online worker and send numeric weights after each frame."""

import os
import resource
import sys
from pathlib import Path

resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_FSIZE, (16 << 20, 16 << 20))
resource.setrlimit(resource.RLIMIT_NOFILE, (128, 128))
sys.path.insert(0, "/opt/core50")
# For author-side detached replay the same trusted files are staged in a temporary directory.
if os.environ.get("PILOT_PUBLIC"):
    sys.path.insert(0, os.environ["PILOT_PUBLIC"])
import numpy as np
import torch
from core_model import Classifier, tensor
from wire import StateLayout

torch.set_num_threads(1)
torch.manual_seed(8107)
model = Classifier().eval()
layout = StateLayout(model)
channel = os.fdopen(os.dup(sys.stdout.fileno()), "wb", buffering=0)
os.dup2(sys.stderr.fileno(), sys.stdout.fileno())
channel.write(b"T")
layout.restore(sys.stdin.buffer.read(layout.numel * 4))
sys.path.insert(0, str(Path.cwd()))
from online import Updater

editor = Updater(model)
channel.write(b"R")
while True:
    data = sys.stdin.buffer.read(32 * 32 * 3)
    if not data:
        break
    if len(data) != 32 * 32 * 3:
        raise ValueError("Incomplete frame")
    image = tensor(np.frombuffer(data, np.uint8).copy().reshape(1, 32, 32, 3))
    model.eval()
    editor.update(image)
    channel.write(layout.encode())
