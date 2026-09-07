#!/usr/bin/env bash
set -euo pipefail

# Start MLflow server in background
echo "Starting MLflow server..."
mlflow server \
  --backend-store-uri sqlite:///mlflow/mlflow.db \
  --default-artifact-root s3://mlflow-artifacts \
  --host 0.0.0.0 \
  --port 5000 &

MLFLOW_PID=$!

# Wait for MLflow to become available (HTTP)
echo "Waiting for MLflow to be responsive..."
python - <<'PY'
import time, sys, urllib.request
for _ in range(60):
    try:
        urllib.request.urlopen('http://127.0.0.1:5000')
        print('MLflow HTTP endpoint is up')
        sys.exit(0)
    except Exception:
        time.sleep(1)
print('MLflow did not start within timeout', file=sys.stderr)
sys.exit(1)
PY

# Ensure the client will talk to the local server unless overridden
export MLFLOW_TRACKING_URI=${MLFLOW_TRACKING_URI:-http://127.0.0.1:5000}

# Run training on the CSV bundled with the image
TRAIN_CSV=${TRAIN_CSV:-donnees.csv}
TRAIN_ARGS=${TRAIN_ARGS:---csv $TRAIN_CSV --train-months 22 --holdout-months 2 --min-train-rows 1}

echo "Running training: python main.py ${TRAIN_ARGS}"
# shellcheck disable=SC2086
python main.py ${TRAIN_ARGS} || echo "Training failed (non-fatal), server will keep running"

# Wait on mlflow server process to keep container alive
wait ${MLFLOW_PID}
