#!/usr/bin/env python3
import csv
import subprocess
import torch
import os
import sys
import multiprocessing
from tqdm import tqdm
from functools import partial
import math
import struct

def choose_architecture(arch="hsw"):
    """Choose one of the available architectures: hsw, ivb, or skl"""
    valid_archs = ["hsw", "ivb", "skl"]
    if arch not in valid_archs:
        print(f"Invalid architecture: {arch}. Choose from: {valid_archs}")
        sys.exit(1)
    
    csv_path = f"bhive/benchmark/throughput/{arch}.csv"
    if not os.path.exists(csv_path):
        print(f"CSV file not found: {csv_path}")
        sys.exit(1)
    
    print(f"Using architecture: {arch}")
    return csv_path

def load_bad_block_ids():
    """Load list of bad block IDs from the may-alias.csv file"""
    bad_block_ids = set()
    may_alias_path = "bhive/benchmark/may-alias.csv"
    
    if os.path.exists(may_alias_path):
        try:
            with open(may_alias_path, 'r') as f:
                for line in f:
                    bad_block_ids.add(line.strip())
            print(f"Loaded {len(bad_block_ids)} bad block IDs to filter")
        except Exception as e:
            print(f"Error loading may-alias.csv: {e}")
    else:
        print(f"Warning: {may_alias_path} not found. No blocks will be filtered.")
    
    return bad_block_ids

def disassemble_block(block_id):
    """Use the disasm tool to turn hex block into human-readable assembly"""
    try:
        result = subprocess.run(
            ["./bhive/benchmark/disasm", block_id],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error disassembling block {block_id}: {e}")
        return None

def tokenize_block(block_id):
    """Use the Ithemal tokenizer to convert the block into XML format"""
    try:
        result = subprocess.run(
            ["./data_collection/build/bin/tokenizer", block_id, "--token"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error tokenizing block {block_id}: {e}")
        return None
    except FileNotFoundError:
        print("Tokenizer not found. Make sure to build the tokenizer first.")
        print("You might need to run: cd data_collection && mkdir build && cd build && cmake .. && make")
        return None

def process_block(row, bad_block_ids):
    """Process a single block and return a data tuple if successful"""
    if len(row) < 2:  # Skip rows without enough columns
        return None
    
    block_id = row[0]
    
    # Check if this block is in the bad block list
    if block_id in bad_block_ids:
        return None
    
    throughput = float(row[1])
    
    # Disassemble the block
    code_intel = disassemble_block(block_id)
    if not code_intel:
        return None
        
    # Tokenize the block
    code_xml = tokenize_block(block_id)
    if not code_xml:
        return None
    
    # Create a tuple with the data
    return (
        block_id,                  # code_id 
        throughput,                # timing (throughput)
        code_intel,                # code_intel (assembly string)
        code_xml                   # code_xml (tokenized XML string)
    )

def process_batch(batch, bad_block_ids):
    """Process a batch of blocks in parallel"""
    results = []
    for row in batch:
        result = process_block(row, bad_block_ids)
        if result:
            results.append(result)
    return results

def process_csv_parallel(csv_path, bad_block_ids, limit=None, num_processes=None):
    """Process the CSV file using multiple processes"""
    # Determine the number of processes to use
    if num_processes is None:
        num_processes = max(1, multiprocessing.cpu_count() - 1)  # Use all but one CPU core
    
    print(f"Using {num_processes} processes for parallel processing")
    
    # Read the CSV file
    try:
        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        if limit:
            rows = rows[:limit]
        
        total_rows = len(rows)
        print(f"Processing {total_rows} blocks...")
        
        # Calculate batch size based on number of processes
        batch_size = math.ceil(total_rows / (num_processes * 4))  # 4 batches per process
        batches = [rows[i:i+batch_size] for i in range(0, total_rows, batch_size)]
        
        # Create a process pool
        with multiprocessing.Pool(processes=num_processes) as pool:
            # Process batches in parallel with progress bar
            process_func = partial(process_batch, bad_block_ids=bad_block_ids)
            results = list(tqdm(
                pool.imap(process_func, batches),
                total=len(batches),
                desc="Processing batches"
            ))
        
        # Flatten the results
        dataset = [item for sublist in results for item in sublist]
        
        # Calculate statistics
        skipped_count = total_rows - len(dataset)
        if skipped_count > 0:
            print(f"Skipped {skipped_count} blocks (filtered or failed processing)")
        
        return dataset
    
    except Exception as e:
        print(f"Error processing CSV: {e}")
        return []

def save_dataset(dataset, arch):
    """Save the dataset as simple binary data"""
    output_file = f"processed_data/bhive_{arch}.data"
    try:
        with open(output_file, 'wb') as f:
            # Write number of items as a 4-byte integer
            f.write(struct.pack('i', len(dataset)))
            
            # For each tuple in the dataset
            for item in dataset:
                block_id, throughput, code_intel, code_xml = item
                
                # Write block_id
                f.write(struct.pack('i', len(block_id)))
                f.write(block_id.encode('utf-8') if isinstance(block_id, str) else block_id)
                
                # Write throughput as float
                f.write(struct.pack('f', float(throughput)))
                
                # Write code_intel
                intel_bytes = code_intel.encode('utf-8')
                f.write(struct.pack('i', len(intel_bytes)))
                f.write(intel_bytes)
                
                # Write code_xml
                xml_bytes = code_xml.encode('utf-8')
                f.write(struct.pack('i', len(xml_bytes)))
                f.write(xml_bytes)
                
        print(f"Dataset saved to {output_file}")
    except Exception as e:
        print(f"Error saving dataset: {e}")

def main():
    # Choose architecture
    if len(sys.argv) > 1:
        arch = sys.argv[1]
    else:
        arch = "hsw"  # Default to Haswell
    
    # Get limit if specified
    limit = None
    if len(sys.argv) > 2:
        try:
            limit = int(sys.argv[2])
        except ValueError:
            print(f"Invalid limit: {sys.argv[2]}. Using all rows.")
    
    # Get number of processes if specified
    num_processes = None
    if len(sys.argv) > 3:
        try:
            num_processes = int(sys.argv[3])
        except ValueError:
            print(f"Invalid number of processes: {sys.argv[3]}. Using default.")
    
    csv_path = choose_architecture(arch)
    
    # Load bad block IDs
    bad_block_ids = load_bad_block_ids()
    
    # Process the CSV in parallel
    print(f"Processing {csv_path}...")
    dataset = process_csv_parallel(csv_path, bad_block_ids, limit, num_processes)
    
    # Save the dataset
    if dataset:
        print(f"Processed {len(dataset)} blocks.")
        save_dataset(dataset, arch)
    else:
        print("No data to save.")

if __name__ == "__main__":
    # Protect the entry point when using multiprocessing
    multiprocessing.freeze_support()
    main() 