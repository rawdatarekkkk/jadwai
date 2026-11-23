"""Merge the PEFT LoRA adapter into Ollama's quantized base GGUF.

No llama.cpp or torch needed: each base tensor is dequantized with gguf-py, the LoRA delta
(alpha / r) * B @ A is added, and the result is written one tensor at a time as Q8_0 (default) or F16.

Why not straight back to Q4_K_M: the delta is only ~0.5% of each weight, and the dequantized base
values sit exactly on the Q4_K grid, so re-quantizing to that same grid snaps ~98% of the weights
back to their old values (measured: 1-2% of the delta survived). Q8_0 keeps it all. merge_candidate.sh
then re-quantizes each tensor to a grid that does not contain its base grid (Q4_K->Q6_K, Q6_K->Q5_K).
Usage: python finetuning/merge_lora.py <base.gguf> <adapter_dir> <out.gguf> [q8_0|f16]
"""
import json
import sys
from pathlib import Path

import gguf
import numpy as np

from lora_to_gguf import NAMES, PATTERN, read_safetensors

SKIP_KEYS = {'GGUF.version', 'GGUF.tensor_count', 'GGUF.kv_count', 'general.architecture', 'general.file_type'}


def main(base_path, adapter_dir, output, out_type='q8_0'):
    q8 = out_type.lower() == 'q8_0'
    adapter_dir = Path(adapter_dir)
    config = json.loads((adapter_dir / 'adapter_config.json').read_text())
    if config.get('use_dora') or config.get('use_rslora') or config.get('modules_to_save'):
        raise SystemExit('Only plain LoRA adapters are supported')
    scale = config['lora_alpha'] / config['r']

    lora = {}
    for name, array in read_safetensors(adapter_dir / 'adapter_model.safetensors'):
        match = PATTERN.match(name)
        if not match or match.group(2) not in NAMES:
            raise SystemExit(f'Unexpected tensor {name}')
        layer, module, part = match.groups()
        lora.setdefault(f'blk.{layer}.{NAMES[module]}.weight', {})[part] = array

    reader = gguf.GGUFReader(base_path)
    arch = reader.fields['general.architecture'].contents()
    writer = gguf.GGUFWriter(output, arch=arch)
    for field in reader.fields.values():
        if field.name in SKIP_KEYS:
            continue
        sub = field.types[1] if field.types[0] == gguf.GGUFValueType.ARRAY else None
        writer.add_key_value(field.name, field.contents(), field.types[0], sub)
    writer.add_file_type(gguf.LlamaFileType.MOSTLY_Q8_0 if q8 else gguf.LlamaFileType.MOSTLY_F16)
    Q8 = gguf.GGMLQuantizationType.Q8_0

    plan = []
    for t in reader.tensors:
        shape = tuple(int(d) for d in reversed(t.shape))  # GGUF stores dims reversed
        dtype = np.float32 if len(shape) == 1 else np.float16
        plan.append((t, shape, dtype))
        if q8 and len(shape) > 1:
            byte_shape = (*shape[:-1], shape[-1] // 32 * 34)  # Q8_0 block: 32 int8 + one f16 scale
            writer.add_tensor_info(t.name, byte_shape, np.dtype(np.uint8), int(np.prod(byte_shape)), raw_dtype=Q8)
        else:
            writer.add_tensor_info(t.name, shape, np.dtype(dtype), int(np.prod(shape)) * np.dtype(dtype).itemsize)
    writer.write_header_to_file()
    writer.write_kv_data_to_file()
    writer.write_ti_data_to_file()

    merged = 0
    for i, (t, shape, dtype) in enumerate(plan, 1):
        w = gguf.quants.dequantize(t.data, t.tensor_type).reshape(shape).astype(np.float32, copy=False)
        if t.name in lora:
            pair = lora.pop(t.name)
            delta = scale * (pair['B'].astype(np.float32) @ pair['A'].astype(np.float32))
            if delta.shape != w.shape:
                raise SystemExit(f'{t.name}: LoRA delta {delta.shape} does not match base {w.shape}')
            w = w + delta
            merged += 1
        writer.write_tensor_data(gguf.quants.quantize(w, Q8) if q8 and len(shape) > 1 else w.astype(dtype))
        print(f'\r{i}/{len(plan)} tensors', end='', flush=True)
    writer.close()
    if lora:
        raise SystemExit(f'{len(lora)} LoRA layers had no matching base tensor, e.g. {next(iter(lora))}')
    print(f'\nmerged {merged} LoRA layers (scale {scale}) -> {output}')


if __name__ == '__main__':
    main(*sys.argv[1:5])
