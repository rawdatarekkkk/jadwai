"""Offline NVIDIA QLoRA training. --check is safe on the current Intel Mac.
Training never uploads data, downloads weights, or changes JAI's active model.
"""
import argparse,hashlib,json,os,platform,sys
from pathlib import Path

def preflight():
 result={'platform':platform.system(),'architecture':platform.machine(),'python':platform.python_version(),'cuda':False}
 try:
  import torch
  result.update(cuda=torch.cuda.is_available(),torch=torch.__version__)
  if result['cuda']:result['gpu']=torch.cuda.get_device_name(0)
 except ImportError:result['torch']='not installed'
 result['ready']=result['platform']=='Linux' and result['cuda']
 result['note']='This pipeline requires a Linux NVIDIA CUDA GPU and pre-downloaded base weights. Intel Mac training is not supported.'
 return result

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');p.add_argument('--base-model',type=Path);p.add_argument('--dataset',type=Path);p.add_argument('--output',type=Path);p.add_argument('--epochs',type=float,default=2);args=p.parse_args();check=preflight()
 print(json.dumps(check,indent=2))
 if args.check:return
 if not check['ready']:raise SystemExit('Training not started: '+check['note'])
 if not all((args.base_model,args.dataset,args.output)):p.error('--base-model, --dataset and --output are required')
 if not (args.base_model/'config.json').is_file():raise SystemExit('Supply the local original Qwen2.5-7B-Instruct HF weights, not Ollama GGUF weights.')
 provenance=json.loads((args.dataset/'provenance.json').read_text())
 for name,sha in provenance['files'].items():
  if hashlib.sha256((args.dataset/name).read_bytes()).hexdigest()!=sha:raise SystemExit('Reviewed dataset export changed')
 if args.output.exists():raise SystemExit('Choose a new output directory; existing training runs are preserved')
 os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',WANDB_DISABLED='true')
 import torch
 from datasets import load_dataset
 from transformers import AutoTokenizer,AutoModelForCausalLM,BitsAndBytesConfig
 from peft import LoraConfig,prepare_model_for_kbit_training
 from trl import SFTConfig,SFTTrainer
 tokenizer=AutoTokenizer.from_pretrained(args.base_model,local_files_only=True)
 if tokenizer.pad_token_id is None:tokenizer.pad_token=tokenizer.eos_token
 dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
 model=AutoModelForCausalLM.from_pretrained(args.base_model,local_files_only=True,device_map={'':0},torch_dtype=dtype,quantization_config=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=dtype))
 model=prepare_model_for_kbit_training(model);model.config.use_cache=False
 adapter=LoraConfig(r=16,lora_alpha=32,lora_dropout=0.05,bias='none',task_type='CAUSAL_LM',target_modules=['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj'])
 dataset=load_dataset('json',data_files=str(args.dataset/'train.jsonl'),split='train')
 for row in dataset:
  length=len(tokenizer.apply_chat_template(row['prompt']+row['completion'],tokenize=True))
  if length>6144:raise SystemExit(f'Example has {length} tokens; exceeds configured 6144. Shorten context or deliberately increase max_length; do not silently truncate labels.')
 # The held-out test file is deliberately not passed to training, checkpoint selection or early stopping.
 config=SFTConfig(output_dir=str(args.output),num_train_epochs=args.epochs,per_device_train_batch_size=1,gradient_accumulation_steps=8,learning_rate=1e-4,max_length=6144,completion_only_loss=True,packing=False,gradient_checkpointing=True,bf16=dtype==torch.bfloat16,fp16=dtype==torch.float16,logging_steps=1,save_strategy='epoch',report_to='none',seed=42)
 trainer=SFTTrainer(model=model,args=config,train_dataset=dataset,processing_class=tokenizer,peft_config=adapter)
 trainer.train();trainer.save_model(str(args.output/'adapter'));tokenizer.save_pretrained(args.output/'adapter')
 (args.output/'training-provenance.json').write_text(json.dumps({'base_model':str(args.base_model.resolve()),'base_config_sha256':hashlib.sha256((args.base_model/'config.json').read_bytes()).hexdigest(),'dataset':provenance,'hardware':check,'epochs':args.epochs,'note':'Adapter only; no production deployment performed'},indent=2))
if __name__=='__main__':main()
