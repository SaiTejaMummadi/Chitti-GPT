#python fineweb.py
#WIll save shards to the local directory "edu_fineweb10B"

import os
import multiprocessing as mp
import numpy as np
import tiktoken 

# !pip install tiktoken
# !pip install datasets
from datasets import load_dataset
from tqdm import tqdm

#----------------
# local_dir = "edu_fineweb10B"
# remote_name = "sample-10BT"
# shard_size = int(1e8) #100M tokens per shard, total of 100 shards

#testing
local_dir = "huggingdata_gptprompts" #$@!changes
shard_size = int(1e4) #10000 tokens per shard, total of 100 shards #$@!changes



#create the cache of the local directory if it doesn't exist yet
# DATA_CACHE_DIR = os.path.join(os.path.dirname(__file__), local_dir)
DATA_CACHE_DIR = os.path.join(os.getcwd(), local_dir)#$@!changes


os.makedirs(DATA_CACHE_DIR, exist_ok = True)

#download the dataset
# fw = load_dataset("HuggingFaceFW/fineweb-edu", name=remote_name, split="train")
fw = load_dataset("zeroshot/twitter-financial-news-sentiment", split="train")#$@!changes
name = "fka_test"

#init the tokenizer
enc = tiktoken.get_encoding("gpt2")
eot = enc._special_tokens['<|endoftext|>'] #end of text token

def tokenize(doc):
    tokens = [eot]
    # tokens.extend(enc.encode_ordinary(doc["text"]))
    tokens.extend(enc.encode_ordinary(doc["text"])) #$@!changes
    tokens_np = np.array(tokens)
    assert (0 <= tokens_np).all() and (tokens_np < 2**16).all(), "tokens dictionary too large"
    tokens_np_uint16 = tokens_np.astype(np.uint16)
    return tokens_np_uint16

def write_datafile(filename, tokens_np):
    np.save(filename, tokens_np)


# tokenize all documents and write output shards, each of shard_size tokens (last shard has remainder)
nprocs = max(1, os.cpu_count() // 2) # don't hog the entire system
token_dtype = np.uint16

with mp.Pool(nprocs) as pool:
    shard_index = 0
    all_tokens_np = np.empty((shard_size,), dtype=token_dtype)
    token_count = 0
    progress_bar = None

    for tokens in pool.imap(tokenize, fw, chunksize=16):

        # is there enough space in the current shard for the new tokens?
        if token_count + len(tokens) < shard_size:
            # simply append tokens to current shard
            all_tokens_np[token_count:token_count+len(tokens)] = tokens
            token_count += len(tokens)
            # update progress bar
            if progress_bar is None:
                progress_bar = tqdm(total=shard_size, unit="tokens", desc=f"Shard {shard_index}")
            progress_bar.update(len(tokens))
        else:
            # write the current shard and start a new one
            split = "val" if shard_index == 0 else "train"
            filename = os.path.join(DATA_CACHE_DIR, f"{name}_{split}_{shard_index:06d}")
            # split the document into whatever fits in this shard; the remainder goes to next one
            remainder = shard_size - token_count
            progress_bar.update(remainder)
            all_tokens_np[token_count:token_count+remainder] = tokens[:remainder]
            write_datafile(filename, all_tokens_np.tolist())
            shard_index += 1
            progress_bar = None
            # populate the next shard with the leftovers of the current doc
            all_tokens_np[0:len(tokens)-remainder] = tokens[remainder:]
            token_count = len(tokens)-remainder
    
    # write any remaining tokens as the last shard
    if token_count != 0:
        split = "val" if shard_index == 0 else "train"
        filename = os.path.join(DATA_CACHE_DIR, f"{name}_{split}_{shard_index:06d}")
        write_datafile(filename, (all_tokens_np[:token_count]).tolist())