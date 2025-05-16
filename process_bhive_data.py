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
import errno # Added for OSError/IOError checking

def choose_architecture(arch="hsw"):
    """Choose one of the available architectures: hsw, ivb, or skl"""
    valid_archs = ["hsw", "ivb", "skl"]
    if arch not in valid_archs:
        print "Invalid architecture: {}. Choose from: {}".format(arch, valid_archs)
        sys.exit(1)
    
    csv_path = "bhive/benchmark/throughput/{}.csv".format(arch)
    if not os.path.exists(csv_path):
        print "CSV file not found: {}".format(csv_path)
        sys.exit(1)
    
    print "Using architecture: {}".format(arch)
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
            print "Loaded {} bad block IDs to filter".format(len(bad_block_ids))
        except Exception as e:
            print "Error loading may-alias.csv: {}".format(e)
    else:
        print "Warning: {} not found. No blocks will be filtered.".format(may_alias_path)
    
    return bad_block_ids

def disassemble_block(block_id):
    """Use the disasm tool to turn hex block into human-readable assembly"""
    try:
        process = subprocess.Popen(
            ["./bhive/benchmark/disasm", block_id],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            # Mimic check=True behavior
            raise subprocess.CalledProcessError(process.returncode, "./bhive/benchmark/disasm", output=stdout)
        return stdout.decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        print "Error disassembling block {}: {}".format(block_id, e)
        return None
    except OSError as e: # For command not found
        print "Error running disasm (command not found?): {}".format(e)
        return None


def tokenize_block(block_id):
    """Use the Ithemal tokenizer to convert the block into XML format"""
    command = ["./data_collection/build/bin/tokenizer", block_id, "--token"]
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
             # Mimic check=True behavior
            raise subprocess.CalledProcessError(process.returncode, command, output=stdout)
        return stdout.decode('utf-8').strip()
    except subprocess.CalledProcessError as e:
        print "Error tokenizing block {}: {}".format(block_id, e)
        return None
    except OSError as e: # For command not found (replaces FileNotFoundError)
        if e.errno == errno.ENOENT:
            print "Tokenizer not found. Make sure to build the tokenizer first."
            print "You might need to run: cd data_collection && mkdir build && cd build && cmake .. && make"
        else:
            print "OSError tokenizing block {}: {}".format(block_id, e)
        return None

def process_block(row, bad_block_ids):
    """Process a single block and return a data tuple if successful"""
    if len(row) < 2:  # Skip rows without enough columns
        return None
    
    block_id = row[0]
    
    # Check if this block is in the bad block list
    if block_id in bad_block_ids:
        return None
    
    try:
        throughput = float(row[1])
    except ValueError:
        # Handle cases where throughput is not a valid float
        print "Warning: Could not convert throughput '{}' to float for block_id '{}'. Skipping.".format(row[1], block_id)
        return None

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
        code_intel,                # code_intel (assembly string - unicode after decode)
        code_xml                   # code_xml (tokenized XML string - unicode after decode)
    )

def process_batch(batch, bad_block_ids):
    """Process a batch of blocks""" # Removed "in parallel" as this function processes one batch
    results = []
    for row in batch:
        result = process_block(row, bad_block_ids)
        if result:
            results.append(result)
    return results

def process_csv_parallel(csv_path, bad_block_ids, limit=None, num_processes=None):
    """Process the CSV file using multiple processes"""
    if num_processes is None:
        try:
            num_cpus = multiprocessing.cpu_count()
            num_processes = max(1, num_cpus - 1) if num_cpus > 1 else 1
        except NotImplementedError:
            num_processes = 1 # Default if cpu_count is not implemented
    
    print "Using {} processes for parallel processing".format(num_processes)
    
    try:
        with open(csv_path, 'r') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        if limit:
            rows = rows[:limit]
        
        total_rows = len(rows)
        if total_rows == 0:
            print "No rows to process."
            return []
        print "Processing {} blocks...".format(total_rows)
        
        # Calculate batch size based on number of processes
        # Ensure float division for Python 2, then ceil and convert to int
        batch_size = int(math.ceil(float(total_rows) / (num_processes * 4)))
        if batch_size == 0: # Avoid batch_size being zero for small total_rows
            batch_size = 1

        batches = [rows[i:i+batch_size] for i in range(0, total_rows, batch_size)]
        
        pool = multiprocessing.Pool(processes=num_processes)
        dataset = []
        try:
            # Process batches in parallel with progress bar
            # partial cannot be directly used with instance methods easily in Pool with complex objects sometimes.
            # bad_block_ids is simple enough.
            process_func = partial(process_batch, bad_block_ids=bad_block_ids)
            
            # pool.imap returns an iterator, tqdm wraps it
            results_iterator = pool.imap(process_func, batches)
            
            # tqdm in Python 2 might need manual update if not behaving with imap well.
            # For simplicity, converting to list with tqdm.
            # Or, iterate and update.
            
            processed_results = []
            for result_batch in tqdm(results_iterator, total=len(batches), desc="Processing batches"):
                processed_results.append(result_batch)

        finally:
            pool.close()
            pool.join()
        
        # Flatten the results
        dataset = [item for sublist in processed_results for item in sublist]
        
        skipped_count = total_rows - len(dataset)
        if skipped_count > 0:
            print "Skipped {} blocks (filtered or failed processing)".format(skipped_count)
        
        return dataset
    
    except Exception as e:
        print "Error processing CSV: {}".format(e)
        import traceback
        traceback.print_exc() # For more detailed error
        return []

def save_dataset(dataset, arch):
    """Save the dataset as simple binary data"""
    output_dir = "processed_data"
    if not os.path.exists(output_dir):
        try:
            os.makedirs(output_dir)
            print "Created directory: {}".format(output_dir)
        except OSError as e:
            if e.errno != errno.EEXIST: # Don't raise if directory already exists (race condition)
                print "Error creating directory {}: {}".format(output_dir, e)
                return # Cannot save if directory cannot be created
                
    output_file = os.path.join(output_dir, "bhive_{}.data".format(arch))
    try:
        torch.save(dataset[1:], output_file)
                
        print "Dataset saved to {}".format(output_file)
    except Exception as e:
        print "Error saving dataset: {}".format(e)
        import traceback
        traceback.print_exc()


def main():
    arch = "hsw"  # Default to Haswell
    if len(sys.argv) > 1:
        arch = sys.argv[1]
    
    limit = None
    if len(sys.argv) > 2:
        try:
            limit = int(sys.argv[2])
        except ValueError:
            print "Invalid limit: {}. Using all rows.".format(sys.argv[2])
    
    num_processes = None
    if len(sys.argv) > 3:
        try:
            num_processes = int(sys.argv[3])
        except ValueError:
            print "Invalid number of processes: {}. Using default.".format(sys.argv[3])
    
    csv_path = choose_architecture(arch)
    if not csv_path: # choose_architecture might sys.exit or return None if error
        return

    bad_block_ids = load_bad_block_ids()
    
    print "Processing {}...".format(csv_path)
    dataset = process_csv_parallel(csv_path, bad_block_ids, limit, num_processes)
    
    if dataset:
        print "Processed {} blocks.".format(len(dataset))
        save_dataset(dataset, arch)
    else:
        print "No data to save."

if __name__ == "__main__":
    if sys.platform.startswith('win'): # More standard check for freeze_support
         multiprocessing.freeze_support()
    main()