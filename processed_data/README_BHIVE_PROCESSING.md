# Processing BHive Data with process_bhive_data.py

This guide explains how to set up and run the `process_bhive_data.py` script to process the BHive dataset for Ithemal.

## Prerequisites

- Ubuntu Linux (tested on Ubuntu 22.04)
- Python 3.10+
- LLVM tools (for disassembly)
- DynamoRIO and the Ithemal tokenizer (for code tokenization)

## Setup

### 1. Install dependencies

```bash
# Install system dependencies
sudo apt update
sudo apt install -y python3-pip llvm

# Install Python dependencies
pip3 install torch tqdm
```

### 2. Build the tokenizer

The tokenizer requires DynamoRIO. If you don't have it already:

```bash
# Clone and build DynamoRIO
cd ~
git clone https://github.com/DynamoRIO/dynamorio.git
cd dynamorio
git submodule init
git submodule update
mkdir build && cd build
cmake ..
make -j$(nproc)

# Set environment variable
export DYNAMORIO_HOME=~/dynamorio
```

Then build the tokenizer:

```bash
# From the Ithemal project root
export ITHEMAL_HOME=$(pwd)
cd data_collection
mkdir -p build && cd build
cmake -DDynamoRIO_DIR=$DYNAMORIO_HOME/build/cmake ..
make -j$(nproc)
```

### 3. Ensure disassembler is executable

```bash
# From project root
chmod +x bhive/benchmark/disasm
```

## Running the Script

### 1. Create output directory

```bash
# From project root
mkdir -p processed_data
```

### 2. Run the script

```bash
# Process data for Haswell architecture (1000 blocks for faster processing)
python3 process_bhive_data.py hsw 1000

# For other architectures:
python3 process_bhive_data.py ivb 1000  # Ivy Bridge
python3 process_bhive_data.py skl 1000  # Skylake
```

By default, the processed data will be saved to the `processed_data/` directory as:
- `bhive_hsw.data` (Haswell)
- `bhive_ivb.data` (Ivy Bridge)
- `bhive_skl.data` (Skylake)

### 3. Run with custom parameters (optional)

```bash
# Syntax:
# python3 process_bhive_data.py [architecture] [limit] [num_processes]

# Examples:
python3 process_bhive_data.py hsw         # Process all available Haswell blocks
python3 process_bhive_data.py hsw 100     # Process only 100 blocks
python3 process_bhive_data.py hsw 1000 8  # Process 1000 blocks using 8 processes
```

## Troubleshooting

### Common Issues

1. **Disassembler errors**:
   - Ensure LLVM is properly installed: `sudo apt install -y llvm`
   - Make sure the disasm script is executable: `chmod +x bhive/benchmark/disasm`
   - Check the disasm script works directly: `./bhive/benchmark/disasm 4889de4889c24c89f7`

2. **Tokenizer errors**:
   - Verify environment variables are set: `echo $ITHEMAL_HOME` and `echo $DYNAMORIO_HOME`
   - Confirm tokenizer binary exists: `ls -la data_collection/build/bin/tokenizer`
   - Test tokenizer directly: `./data_collection/build/bin/tokenizer 4889de4889c24c89f7 --token`

3. **No output files**:
   - Ensure the processed_data directory exists: `mkdir -p processed_data`
   - Check for write permissions: `touch processed_data/test && rm processed_data/test`

## What the Script Does

1. Loads bad block IDs from the may-alias.csv file (to filter problematic blocks)
2. Reads code blocks from the architecture-specific CSV file (hsw.csv, ivb.csv, or skl.csv)
3. For each block:
   - Disassembles it using the llvm-mc disassembler
   - Tokenizes it using the Ithemal tokenizer
   - Creates a tuple of (block_id, throughput, code_intel, code_xml)
4. Saves the processed data as a PyTorch serialized file (.data) 