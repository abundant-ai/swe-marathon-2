"""Manually launch the full-model H100 learning experiment; never used by CI."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import modal
from dotenv import dotenv_values

TASK = Path(__file__).resolve().parents[1]
LIBRARY = Path('/Users/eric/Desktop/titans')
sys.path.insert(0, str(TASK / 'common'))
from titans_task.experiment import run_experiment  # noqa: E402

credentials = dotenv_values(TASK.parents[2] / '.env') if modal.is_local() else {}
secret = modal.Secret.from_dict({key: value for key, value in credentials.items()
                                 if key in {'WANDB_API_KEY', 'WANDB_ENTITY'} and value})
app = modal.App('titans-scratch-learning')
volume = modal.Volume.from_name('titans-learning-runs', create_if_missing=True)
image = (modal.Image.debian_slim(python_version='3.12').apt_install('g++')
         .pip_install('torch==2.9.1', 'transformers==4.57.1', 'liger-kernel==0.6.4',
                      'safetensors>=0.4.5', 'wandb==0.23.1', 'sentencepiece>=0.2')
         .env({'PYTHONPATH': '/workspace:/workspace/common', 'TOKENIZERS_PARALLELISM': 'false',
               'TORCHINDUCTOR_CACHE_DIR': '/runs/inductor'})
         .add_local_dir(LIBRARY / 'titans', '/workspace/titans')
         .add_local_dir(TASK / 'common', '/workspace/common')
         .add_local_dir(TASK / 'experiment/data/train', '/data/train')
         .add_local_dir(TASK / 'experiment/data/public', '/data/public')
         .add_local_dir(TASK / 'experiment/data/tokenizer', '/data/tokenizer'))
remote_run = app.function(image=image, gpu='H100!', cpu=8, memory=65536, timeout=21600,
                          max_containers=1, volumes={'/runs': volume}, secrets=[secret])(run_experiment)


@app.local_entrypoint()
def main(smoke: bool = False, diagnostic: bool = False, stable_memory: bool = False) -> None:
    """Launch a two-step preflight or three-hour run and save its remote handle.

    Args:
        smoke: Restrict the preflight to two optimizer steps and prefix probes.
        diagnostic: Run at most twenty steps to investigate numerical behavior.
        stable_memory: Test reduced inner learning rate and initial forget gate.
    """
    name = ('smoke-' if smoke else 'diagnostic-' if diagnostic else 'scratch-3h-') + datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    call = remote_run.spawn(name, hours=3.0, max_steps=2 if smoke else 20 if diagnostic else 2560,
                           full_eval=not (smoke or diagnostic), stable_memory=stable_memory)
    handle = {'run_name': name, 'call_id': call.object_id, 'app_id': app.app_id}
    (TASK / 'experiment' / f'{name}.handle.json').write_text(json.dumps(handle, indent=2))
    print(json.dumps(handle), flush=True)
    print(json.dumps(call.get(), indent=2), flush=True)
