"""Convert the PEFT LoRA adapter from colab_train.ipynb into a llama.cpp GGUF adapter.

Needs only `gguf` and `numpy` (no torch). Usage:
    python finetuning/lora_to_gguf.py finetuning/models/jai-lora finetuning/models/jai-lora.gguf
The result can be merged into the Ollama base model with `llama-export-lora` (see merge_candidate.sh).
"""
import json
import re
import struct
import sys
from pathlib import Path

import gguf
import numpy as np

NAMES = {
    'self_attn.q_proj': 'attn_q', 'self_attn.k_proj': 'attn_k', 'self_attn.v_proj': 'attn_v',
    'self_attn.o_proj': 'attn_output', 'mlp.gate_proj': 'ffn_gate', 'mlp.up_proj': 'ffn_up',
    'mlp.down_proj': 'ffn_down',
}
PATTERN = re.compile(r'^base_model\.model\.model\.layers\.(\d+)\.(self_attn\.\w+|mlp\.\w+)\.lora_([AB])\.weight$')
DTYPES = {'F32': np.float32, 'F16': np.float16}


def read_safetensors(path):
    with open(path, 'rb') as f:
        size = struct.unpack('<Q', f.read(8))[0]
        header = json.loads(f.read(size))
    header.pop('__metadata__', None)
    raw = np.memmap(path, dtype=np.uint8, mode='r', offset=8 + size)
    for name, info in header.items():
        if info['dtype'] not in DTYPES:
            raise SystemExit(f'{name}: unsupported dtype {info["dtype"]}')
        start, end = info['data_offsets']
        yield name, np.frombuffer(raw[start:end], dtype=DTYPES[info['dtype']]).reshape(info['shape'])


def main(adapter_dir, output):
    adapter_dir = Path(adapter_dir)
    config = json.loads((adapter_dir / 'adapter_config.json').read_text())
    if config.get('use_dora') or config.get('use_rslora') or config.get('modules_to_save'):
        raise SystemExit('Only plain LoRA adapters are supported')
    writer = gguf.GGUFWriter(output, arch='qwen2')
    writer.add_type(gguf.GGUFType.ADAPTER)
    writer.add_string(gguf.Keys.Adapter.TYPE, 'lora')
    writer.add_float32(gguf.Keys.Adapter.LORA_ALPHA, float(config['lora_alpha']))
    count = 0
    for name, array in sorted(read_safetensors(adapter_dir / 'adapter_model.safetensors')):
        match = PATTERN.match(name)
        if not match or match.group(2) not in NAMES:
            raise SystemExit(f'Unexpected tensor {name}')
        layer, module, part = match.groups()
        writer.add_tensor(f'blk.{layer}.{NAMES[module]}.weight.lora_{part.lower()}', np.ascontiguousarray(array, dtype=np.float32))
        count += 1
    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_tensors_to_file()
    writer.close()
    print(f'wrote {count} tensors, alpha {config["lora_alpha"]}, rank {config["r"]} -> {output}')


if __name__ == '__main__':
    main(*sys.argv[1:3])
