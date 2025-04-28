#!/usr/bin/env python3
import csv
import subprocess
import torch
import os
import sys
from tqdm import tqdm

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

def process_csv(csv_path, limit=None):
    """Process each row in the CSV file and create data tuples"""
    dataset = []
    
    try:
        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            rows = list(reader)
            
        if limit:
            rows = rows[:limit]
            
        for row in tqdm(rows, desc="Processing blocks"):
            if len(row) >= 2:  # Make sure the row has at least 2 columns
                block_id = row[0]
                throughput = float(row[1])
                
                # Disassemble the block
                code_intel = disassemble_block(block_id)
                if not code_intel:
                    continue
                    
                # Tokenize the block
                code_xml = tokenize_block(block_id)
                if not code_xml:
                    continue
                
                # Create a tuple with the data
                data_tuple = (
                    block_id,                  # code_id 
                    throughput,                # timing (throughput)
                    code_intel,                # code_intel (assembly string)
                    code_xml                   # code_xml (tokenized XML string)
                )
                
                dataset.append(data_tuple)
                
    except Exception as e:
        print(f"Error processing CSV: {e}")
    
    return dataset

def save_dataset(dataset, arch):
    """Save the dataset using torch.save()"""
    output_file = f"bhive_{arch}.data"
    try:
        torch.save(dataset, output_file)
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
    
    csv_path = choose_architecture(arch)
    
    # Process the CSV
    print(f"Processing {csv_path}...")
    dataset = process_csv(csv_path, limit)
    
    # Save the dataset
    if dataset:
        print(f"Processed {len(dataset)} blocks.")
        save_dataset(dataset, arch)
    else:
        print("No data to save.")

if __name__ == "__main__":
    main() 