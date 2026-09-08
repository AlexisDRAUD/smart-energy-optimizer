"""Supervise the tracking server and optional training in the same container."""

from __future__ import annotations

import os
import shlex
import signal
import subprocess
import sys
import time
from contextlib import suppress
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


def main() -> int:
    children: list[subprocess.Popen] = []

    def stop(signum: int, _frame: object) -> None:
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    enabled = os.getenv("ML_TRAIN_ON_START", "1")
    if enabled not in {"0", "1"}:
        raise ValueError("ML_TRAIN_ON_START must be 0 or 1")
    timeout = int(os.getenv("MLFLOW_START_TIMEOUT_SECONDS", "120"))
    if timeout <= 0:
        raise ValueError("MLFLOW_START_TIMEOUT_SECONDS must be positive")
    Path("/mlflow").mkdir(parents=True, exist_ok=True)
    os.environ["MLFLOW_TRACKING_URI"] = "http://127.0.0.1:5000"
    os.environ["ML_TRAIN_LOCK_PATH"] = "/mlflow/training.lock"
    try:
        server = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-m",
                "mlflow",
                "server",
                "--app-name",
                "enervision",
                "--allowed-hosts",
                "localhost,localhost:*,127.0.0.1,127.0.0.1:*,mlflow,mlflow:5000",
                "--backend-store-uri",
                "sqlite:////mlflow/mlflow.db",
                "--serve-artifacts",
                "--artifacts-destination",
                "s3://mlflow-artifacts",
                "--default-artifact-root",
                "mlflow-artifacts:/",
                "--host",
                "127.0.0.1",
                "--port",
                "5000",  # noqa: S104
            ],
            start_new_session=True,
        )
        children.append(server)
        deadline = time.monotonic() + timeout
        while True:
            if server.poll() is not None:
                return server.returncode or 1
            try:
                with urlopen("http://127.0.0.1:5000/health", timeout=2):  # noqa: S310
                    break
            except (URLError, TimeoutError):
                if time.monotonic() >= deadline:
                    raise RuntimeError("MLflow readiness deadline exceeded") from None
                time.sleep(1)
        if enabled == "1":
            training = subprocess.Popen(  # noqa: S603
                [sys.executable, "/app/main.py", *shlex.split(os.getenv("TRAIN_ARGS", ""))],
                start_new_session=True,
            )
            children.append(training)
            while training.poll() is None:
                if server.poll() is not None:
                    return server.returncode or 1
                time.sleep(0.5)
            if training.returncode:
                return training.returncode
        return server.wait()
    finally:
        for child in reversed(children):
            with suppress(ProcessLookupError):
                os.killpg(child.pid, signal.SIGTERM)
        deadline = time.monotonic() + 10
        for child in reversed(children):
            try:
                child.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                child.wait()


if __name__ == "__main__":
    raise SystemExit(main())
