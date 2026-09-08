"""MLflow's supported mlflow.app extension; no separate server or frontend build."""

import fcntl
import os
import secrets
import subprocess
import sys
import threading
from functools import wraps
from pathlib import Path

from flask import jsonify, make_response, request
from mlflow import MlflowClient
from mlflow.server import app
from sqlalchemy import create_engine, text

EXPERIMENT = "EnerVision_Manual_Training"
TRACKING_URI = "http://127.0.0.1:5000"


def client():
    # MLflow's server handlers change MLFLOW_TRACKING_URI to the backend SQLite
    # URI inside workers. Never inherit that value for client calls or training.
    return MlflowClient(tracking_uri=TRACKING_URI)


def lock_training():
    # Ownership passes to the caller and then the training subprocess.
    lock = Path(os.getenv("ML_TRAIN_LOCK_PATH", "/mlflow/training.lock")).open("w")  # noqa: SIM115
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        return None
    return lock


def sites():
    engine = create_engine(os.environ["DATABASE_URL"])
    try:
        with engine.connect() as connection:
            return [
                str(row[0])
                for row in connection.execute(
                    text(
                        "SELECT DISTINCT site_id FROM readings WHERE consumption_kwh IS NOT NULL "
                        "ORDER BY site_id"
                    )
                )
            ]
    finally:
        engine.dispose()


def api_errors(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception:
            app.logger.exception("Training API failed")
            return jsonify(error="MLflow unavailable; check container logs and retry."), 503

    return wrapped


def create_flask_app():
    @app.after_request
    def navigation(response):
        # Modify only the HTML shell, never MLflow's bundled JS or API responses.
        if request.path == "/" and response.status_code == 200:
            response.direct_passthrough = False
            html = response.get_data(as_text=True)
            response.set_data(
                html.replace(
                    "</body>",
                    (
                        '<a href="/training" style="position:fixed;bottom:16px;right:24px;'
                        "z-index:10000;background:#174ea6;color:white;padding:12px;"
                        'border-radius:6px">Entraîner un modèle</a></body>'
                    ),
                )
            )
            response.headers.pop("ETag", None)
        return response

    @app.get("/training")
    def training_page():
        token = secrets.token_urlsafe(32)
        response = make_response(
            Path("/app/training.html").read_text().replace("__CSRF_TOKEN__", token)
        )
        response.set_cookie(
            "training_csrf",
            token,
            httponly=True,
            samesite="Strict",
            secure=request.is_secure,
            path="/training",
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.get("/training/api/sites")
    def list_sites():
        try:
            return jsonify(sites())
        except Exception:
            app.logger.exception("Cannot list training sites")
            return jsonify(error="Database unavailable; check container logs."), 503

    @app.get("/training/api/jobs")
    @api_errors
    def jobs():
        c = client()
        experiment = c.get_experiment_by_name(EXPERIMENT)
        if not experiment:
            return jsonify([])
        runs = c.search_runs(
            [experiment.experiment_id], max_results=30, order_by=["attributes.start_time DESC"]
        )
        # A terminated container cannot leave its jobs appearing active forever.
        lock = lock_training()
        try:
            output = []
            experiment_ids = [e.experiment_id for e in c.search_experiments()]
            for run in runs:
                if lock and run.info.status == "RUNNING":
                    # The run may have finished between search_runs and taking the lock.
                    run = c.get_run(run.info.run_id)
                    if run.info.status == "RUNNING":
                        c.set_tag(
                            run.info.run_id, "training.error", "Training process interrupted."
                        )
                        c.set_terminated(run.info.run_id, "FAILED")
                        run = c.get_run(run.info.run_id)
                children = c.search_runs(
                    experiment_ids=experiment_ids,
                    filter_string=f"tags.mlflow.parentRunId = '{run.info.run_id}'",
                    max_results=100,
                )
                if lock and run.info.status == "FAILED":
                    for child in children:
                        if child.info.status == "RUNNING":
                            c.set_terminated(child.info.run_id, "FAILED")
                output.append(
                    dict(
                        run_id=run.info.run_id,
                        experiment_id=run.info.experiment_id,
                        status=run.info.status,
                        error=run.data.tags.get("training.error"),
                        models=[
                            dict(
                                run_id=r.info.run_id,
                                experiment_id=r.info.experiment_id,
                                metrics=r.data.metrics,
                                site=r.data.params.get("site_id"),
                            )
                            for r in children
                        ],
                    )
                )
            return jsonify(output)
        finally:
            if lock:
                lock.close()

    @app.post("/training/api/jobs")
    @api_errors
    def launch():
        origin = request.headers.get("Origin")
        cookie = request.cookies.get("training_csrf", "")
        token = request.headers.get("X-CSRF-Token", "")
        if (
            origin != request.host_url.rstrip("/")
            or not cookie
            or not secrets.compare_digest(cookie, token)
        ):
            return jsonify(error="Invalid origin or CSRF token; reload the training page."), 403
        data = request.get_json(silent=True)
        if not isinstance(data, dict) or set(data) != {"site_id", "estimator", "holdout_minutes"}:
            return jsonify(error="Expected site_id, estimator and holdout_minutes."), 400
        if (
            data["estimator"] not in ("random_forest", "extra_trees")
            or type(data["holdout_minutes"]) is not int
            or not 1 <= data["holdout_minutes"] <= 525600
            or not isinstance(data["site_id"], str)
        ):
            return jsonify(error="Invalid estimator, site or holdout (1–525600 minutes)."), 400
        try:
            if data["site_id"] not in sites():
                return jsonify(error="Unknown site or no readings."), 400
        except Exception:
            return jsonify(error="Database unavailable; check container logs."), 503
        lock = lock_training()
        if not lock:
            return jsonify(error="Another training is running; wait for it to finish."), 409
        run = None
        c = None
        try:
            c = client()
            experiment = c.get_experiment_by_name(EXPERIMENT)
            experiment_id = (
                experiment.experiment_id if experiment else c.create_experiment(EXPERIMENT)
            )
            run = c.create_run(
                experiment_id,
                tags={"mlflow.runName": "Manual training", "training.source": "integrated-ui"},
            )
            c.log_param(run.info.run_id, "site_id", data["site_id"])
            c.log_param(run.info.run_id, "estimator", data["estimator"])
            process = subprocess.Popen(  # noqa: S603
                [
                    sys.executable,
                    "/app/main.py",
                    "--site-id",
                    data["site_id"],
                    "--experiment",
                    "EnerVision_UI_Models",
                    "--estimator",
                    data["estimator"],
                    "--holdout-minutes",
                    str(data["holdout_minutes"]),
                    "--no-production-alias",
                    "--job-run-id",
                    run.info.run_id,
                ],
                env={
                    **os.environ,
                    "MLFLOW_TRACKING_URI": TRACKING_URI,
                    "ML_TRAIN_LOCK_FD": str(lock.fileno()),
                },
                pass_fds=(lock.fileno(),),
            )
            threading.Thread(target=process.wait, daemon=True).start()
            return jsonify(run_id=run.info.run_id), 202
        except Exception:
            app.logger.exception("Training launch failed")
            if run:
                c.set_tag(run.info.run_id, "training.error", "Unable to start training process.")
                c.set_terminated(run.info.run_id, "FAILED")
            return jsonify(error="Unable to start training; check container logs."), 503
        finally:
            lock.close()

    return app


def create_app():
    from mlflow.server.fastapi_app import create_fastapi_app

    return create_fastapi_app(create_flask_app())
