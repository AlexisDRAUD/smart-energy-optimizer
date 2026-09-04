from __future__ import annotations

import os
from typing import Any

import mlflow
import mlflow.pyfunc
import pandas as pd
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool

app = FastAPI()

tracking_uri = os.getenv("MLFLOW_TRACKING_URI")
if tracking_uri:
    mlflow.set_tracking_uri(tracking_uri)

MODEL_URI = os.getenv("MLFLOW_MODEL_URI", "models:/EnerVision_RF_Predictor/latest")
model = mlflow.pyfunc.load_model(MODEL_URI)


@app.post("/predict")
async def predict(payload: dict[str, Any]) -> dict[str, float]:
    df = pd.DataFrame([payload])
    pred = await run_in_threadpool(model.predict, df)
    return {"predicted_consumption_kw": float(pred[0])}
