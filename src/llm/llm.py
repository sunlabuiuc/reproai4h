import transformers
import torch
from transformers import BitsAndBytesConfig, pipeline, AutoTokenizer

def generate_text_with_icl(prompt, pipeline, task_examples, max_new_tokens=256, temperature=0.00001, top_p=0.99) -> str:
    """
    Generate text using the specified prompt and parameters with in-context learning.
    Args:
    prompt (str): The input prompt for text generation.
    pipeline: The text generation pipeline.
    task_examples (list): List of dictionaries containing input-output pairs for in-context learning.
    max_new_tokens (int, optional): The maximum number of new tokens to generate. Defaults to 256.
    temperature (float, optional): The temperature value for sampling. Defaults to 0.00001.
    top_p (float, optional): The top-p value for sampling. Defaults to 0.99.
    Returns:
    str: The generated text.
    """
    # Construct the in-context learning prompt
    icl_prompt = "You are an expert and experienced from the healthcare and biomedical domain with extensive medical knowledge and practical experience. Your job is to help annotate specific tasks by looking for common patterns within text."
    if len(task_examples) > 0:
        icl_prompt += " Here are some examples of how to perform the task:\n\n"
        
        for example in task_examples:
            icl_prompt += f"Input: {example['input']}\nOutput: {example['output']}\n\n"
    
    icl_prompt += f"Now, please perform the same task for the following input:\nInput: {prompt}\nOutput:"

    messages = [
        {"role": "system", "content": icl_prompt},
        {"role": "user", "content": prompt},
    ]
    
    full_prompt = pipeline.tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )
    
    terminators = [
        pipeline.tokenizer.eos_token_id,
        pipeline.tokenizer.convert_tokens_to_ids("<|eot_id|>")
    ]
    
    outputs = pipeline(
        full_prompt,
        max_new_tokens=max_new_tokens,
        eos_token_id=terminators,
        do_sample=True,
        temperature=temperature,
        top_p=top_p,
    )
    
    return outputs[0]["generated_text"][len(full_prompt):]



def load_70b_model(device):
    ACCESS_TOKEN = ""
    model_id = "aaditya/OpenBioLLM-Llama3-70B"
        # Load model directly

    nf4_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_use_double_quant=True,
        bnb_4bit_compute_dtype=torch.bfloat16
    )
    model_nf4 = transformers.AutoModelForCausalLM.from_pretrained(model_id, 
                                                    quantization_config=nf4_config,
                                                    device_map={"": device},
                                                    token=ACCESS_TOKEN)
    
    tokenizer = AutoTokenizer.from_pretrained(model_id, token=ACCESS_TOKEN)
    
    pipeline = transformers.pipeline(
        "text-generation",
        model= model_nf4, #model_id,
        # model_kwargs={"torch_dtype": torch.bfloat16},
        tokenizer=tokenizer,
        # device=device,
    )

    messages = [
        {"role": "system", "content": "You are an expert and experienced from the healthcare and biomedical domain with extensive medical knowledge and practical experience. Your name is OpenBioLLM, and your job is to annotate medically-relevant data. Please answer the below message."},
        {"role": "user", "content": "Hello?"},
    ]

    prompt = pipeline.tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    terminators = [
        pipeline.tokenizer.eos_token_id,
        pipeline.tokenizer.convert_tokens_to_ids("<|eot_id|>")
    ]

    outputs = pipeline(
        prompt,
        max_new_tokens=256,
        eos_token_id=terminators,
        do_sample=True,
        temperature=0.1,
        top_p=0.9,
    )
    print(outputs[0]["generated_text"][len(prompt):])
    return pipeline