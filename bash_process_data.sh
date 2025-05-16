echo "Loading LLVM module"
module load llvm
echo "LLVM version:"
llvm-config --version

# hsw, ivb, skl
NUM_THREADS=10

python process_bhive_data.py hsw 0 $NUM_THREADS
python process_bhive_data.py ivb 0 $NUM_THREADS
python process_bhive_data.py skl 0 $NUM_THREADS