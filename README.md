# Ithemal

**Ithemal** is a data‑driven neural model that estimates the *throughput* (CPU cycles) of x86‑64 basic blocks with high accuracy, portability, and speed.

> Mendis *et al.* “Ithemal: Accurate, Portable and Fast Basic Block Throughput Estimation using Deep Neural Networks.” *ICML 2019*
> [\[arXiv\]](https://arxiv.org/abs/1808.07412)  [\[BibTeX\]](http://groups.csail.mit.edu/commit/bibtex.cgi?key=ithemal-icml)

---

## Quick Start

### 1 · Install dependencies

```bash
# clone the repository (add --recursive if you plan to retrain)
git clone https://github.com/YuxuanMa-sys/cs521_Ithemal.git
cd cs521_Ithemal

# create a dedicated env and install requirements
conda create -n ithemal --file env
conda activate ithemal
```

### 2 · Configure environment

```bash
# point ITHEMAL_HOME to the repo root (edit the path as needed)
export ITHEMAL_HOME="/path/to/cs521_Ithemal"
```

### 3 · Download data

Pre‑processed datasets for three micro‑architectures are available:

| µArch      | File             | Size   |
| ---------- | ---------------- | ------ |
| Haswell    | `bhive_hsw.data` | 254 MB |
| Ivy Bridge | `bhive_ivb.data` | 246 GB |
| Skylake    | `bhive_skl.data` | 243 GB |

Download the bundle from **Google Drive** and extract it anywhere:

[📦 Ithemal datasets](https://drive.google.com/file/d/1lr7k0Gomd2tHEvAw-jwRFFqnTcs4Rfg4/view?usp=sharing)

> **Need to regenerate?** Install LLVM (≥3.11) and run:
>
> ```bash
> bash bash_process_data.sh
> ```

---

## Pre‑trained Models & Prediction

Pre‑trained models matching the paper are hosted in a separate repository:

* **Haswell** – [`paper/haswell/`](https://github.com/psg-mit/Ithemal-models/blob/master/paper/haswell)
* **Skylake** – [`paper/skylake/`](https://github.com/psg-mit/Ithemal-models/blob/master/paper/skylake)
* **Ivy Bridge** – [`paper/ivybridge/`](https://github.com/psg-mit/Ithemal-models/blob/master/paper/ivybridge)

```bash
python learning/pytorch/ithemal/predict.py \
    --model predictor.dump \
    --model-data trained.mdl \
    --file my_binary.o \
    --verbose
```

The script follows the same annotation convention as **IACA**. Example annotated binaries are under `learning/pytorch/examples/`.

---

## Training from Scratch

```bash
python learning/pytorch/ithemal/run_ithemal.py \
    --data ./processed_data/bhive_hsw.data \
    --use-rnn train \
    --experiment-name my_exp \
    --experiment-time $(date +%Y%m%d_%H%M%S) \
    --sgd --threads 4 --trainers 6 \
    --weird-lr --decay-lr --epochs 100
```

**Outputs** (under `learning/pytorch/saved/<EXPNAME>/<TIME>/`):

* `loss_report.log` – tab‑separated training progress
* `validation_results.txt` – `predicted,actual` pairs for the test set
* `trained.mdl` – learned weights
* `predictor.dump` – architecture & vocab (use with `predict.py`)


or you can just run the provided script:

```bash
bash bash_train.sh
```
---

## Repository Layout

```
learning/
└── pytorch/
    ├── ithemal/         # CLI & training drivers
    ├── models/          # Model definitions & optimizers
    ├── data/            # Dataset loaders & batching
common/
└── common_libs/
    └── utilities.py     # Instruction & basic‑block representation

data_collection/
├── tokenizer/           # Canonicalization & tokenization (C)
└── common/
```

---