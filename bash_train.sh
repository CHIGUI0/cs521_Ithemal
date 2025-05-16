
set -e

DATA_TYPE="skl"
DATA_FILE="./processed_data/bhive_${DATA_TYPE}.data"
EXP_NAME=$DATA_TYPE
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

THREADS=4
TRAINERS=6
EPOCHS=10

python "$ITHEMAL_HOME/learning/pytorch/ithemal/run_ithemal.py" \
  --data "$DATA_FILE"               \
  --use-rnn                         \
  train                             \
  --experiment-name  "$EXP_NAME"    \
  --experiment-time  "$TIMESTAMP"   \
  --sgd --threads "$THREADS" --trainers "$TRAINERS" \
  --weird-lr --decay-lr --epochs "$EPOCHS"
