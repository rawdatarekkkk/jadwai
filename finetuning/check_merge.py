"""Check how much of the LoRA training survived in the jai-candidate Ollama model.

For every trained matrix, compares (candidate - base) with the intended delta (alpha / r) * B @ A.
'kept' near 1.0 means the training is present; near 0 means quantization erased it.
Usage: python finetuning/check_merge.py [candidate] [adapter_dir]
"""
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import gguf
import numpy as np

from lora_to_gguf import NAMES, PATTERN, read_safetensors


def blob(model):
    out = subprocess.check_output(['ollama', 'show', model, '--modelfile'], text=True)
    return next(line.split(' ', 1)[1].strip() for line in out.splitlines() if line.startswith('FROM /'))


def main(candidate='jai-candidate', adapter_dir='finetuning/models/jai-lora'):
    adapter_dir = Path(adapter_dir)
    config = json.loads((adapter_dir / 'adapter_config.json').read_text())
    scale = config['lora_alpha'] / config['r']
    lora = defaultdict(dict)
    for name, array in read_safetensors(adapter_dir / 'adapter_model.safetensors'):
        layer, module, part = PATTERN.match(name).groups()
        lora[f'blk.{layer}.{NAMES[module]}.weight'][part] = array
    base = {t.name: t for t in gguf.GGUFReader(blob('qwen2.5:7b-instruct')).tensors}
    cand = {t.name: t for t in gguf.GGUFReader(blob(candidate)).tensors}
    by_kind = defaultdict(list)
    for name, pair in sorted(lora.items()):
        b, c = base[name], cand[name]
        shape = tuple(int(x) for x in reversed(b.shape))
        got = (gguf.quants.dequantize(c.data, c.tensor_type).reshape(shape)
               - gguf.quants.dequantize(b.data, b.tensor_type).reshape(shape)).ravel()
        want = (scale * (pair['B'] @ pair['A'])).ravel()
        kept = float(got @ want / (want @ want))
        by_kind[f'{name.split(".")[2]} {b.tensor_type.name}->{c.tensor_type.name}'].append(kept)
    worst = 1.0
    for kind, values in sorted(by_kind.items()):
        print(f'{kind:28s} layers={len(values):2d} kept mean={np.mean(values):.2f} min={np.min(values):.2f}')
        worst = min(worst, float(np.min(values)))
    print('OK: training present in every trained matrix' if worst > 0.7 else 'PROBLEM: some trained matrices lost the training')


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).parent))
    main(*sys.argv[1:3])
