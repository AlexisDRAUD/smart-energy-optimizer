import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location(
    "training_ui", Path(__file__).parents[1] / "ui" / "training_ui.py"
)
ui = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ui
spec.loader.exec_module(ui)


@pytest.fixture(scope="module")
def app():
    return ui.create_flask_app()


@pytest.fixture
def browser(app, monkeypatch):
    monkeypatch.setattr(ui, "sites", lambda: ["one"])
    browser = app.test_client()
    browser.set_cookie("training_csrf", "test-token", path="/training")
    return browser


def post(browser, **changes):
    payload = {"site_id": "one", "estimator": "extra_trees", "holdout_minutes": 120}
    payload.update(changes)
    return browser.post(
        "/training/api/jobs",
        json=payload,
        headers={"Origin": "http://localhost", "X-CSRF-Token": "test-token"},
    )


def test_csrf_and_invalid_inputs(browser):
    assert browser.post("/training/api/jobs", json={}).status_code == 403
    assert (
        browser.post(
            "/training/api/jobs",
            json={},
            headers={"Origin": "https://other.example", "X-CSRF-Token": "test-token"},
        ).status_code
        == 403
    )
    for changes in (
        {"site_id": "missing"},
        {"estimator": "shell"},
        {"holdout_minutes": 0},
        {"holdout_minutes": True},
        {"holdout_minutes": "120"},
    ):
        assert post(browser, **changes).status_code == 400


def test_sites_and_concurrency(browser, monkeypatch):
    assert browser.get("/training/api/sites").json == ["one"]
    monkeypatch.setattr(ui, "lock_training", lambda: None)
    assert post(browser).status_code == 409


def test_launch_and_launch_failure(browser, monkeypatch):
    c = Mock()
    c.get_experiment_by_name.return_value = SimpleNamespace(experiment_id="1")
    c.create_run.return_value = SimpleNamespace(info=SimpleNamespace(run_id="abc"))
    monkeypatch.setattr(ui, "client", lambda: c)
    lock = Mock()
    lock.fileno.return_value = 7
    monkeypatch.setattr(ui, "lock_training", lambda: lock)
    spawn = Mock()
    monkeypatch.setattr(ui.subprocess, "Popen", spawn)
    assert post(browser).status_code == 202
    command = spawn.call_args.args[0]
    assert "--no-production-alias" in command
    assert command[command.index("--site-id") + 1] == "one"
    assert spawn.call_args.kwargs["pass_fds"] == (7,)
    assert spawn.call_args.kwargs["env"]["MLFLOW_TRACKING_URI"] == ui.TRACKING_URI
    lock.close.assert_called_once()
    spawn.side_effect = OSError("launch failure")
    assert post(browser).status_code == 503
    c.set_terminated.assert_called_with("abc", "FAILED")


def test_database_failure(browser, monkeypatch):
    monkeypatch.setattr(ui, "sites", Mock(side_effect=RuntimeError("secret-db-url")))
    response = post(browser)
    assert response.status_code == 503
    assert "secret-db-url" not in response.text


def test_shell_navigation(browser):
    response = browser.get("/")
    assert response.status_code == 200
    assert 'href="/training"' in response.text


@pytest.mark.parametrize("current_status", ["RUNNING", "FINISHED"])
def test_job_reconciliation_rechecks_status(browser, monkeypatch, current_status):
    def run(status):
        return SimpleNamespace(
            info=SimpleNamespace(run_id="abc", experiment_id="1", status=status),
            data=SimpleNamespace(tags={}, metrics={}, params={}),
        )

    c = Mock()
    c.get_experiment_by_name.return_value = SimpleNamespace(experiment_id="1")
    c.search_experiments.return_value = [SimpleNamespace(experiment_id="1")]
    c.search_runs.side_effect = [[run("RUNNING")], []]
    c.get_run.side_effect = [run(current_status), run("FAILED")]
    monkeypatch.setattr(ui, "client", lambda: c)
    lock = Mock()
    monkeypatch.setattr(ui, "lock_training", lambda: lock)
    response = browser.get("/training/api/jobs")
    assert response.status_code == 200
    if current_status == "RUNNING":
        c.set_terminated.assert_called_once_with("abc", "FAILED")
        assert response.json[0]["status"] == "FAILED"
    else:
        c.set_terminated.assert_not_called()
        assert response.json[0]["status"] == "FINISHED"
    lock.close.assert_called_once()


def test_tracking_unavailable_is_clear(browser, monkeypatch):
    monkeypatch.setattr(ui, "client", Mock(side_effect=RuntimeError("private details")))
    response = browser.get("/training/api/jobs")
    assert response.status_code == 503
    assert response.json["error"].startswith("MLflow unavailable")


def test_client_ignores_server_mutated_tracking_uri(monkeypatch):
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "sqlite:///server.db")
    constructor = Mock()
    monkeypatch.setattr(ui, "MlflowClient", constructor)
    ui.client()
    constructor.assert_called_once_with(tracking_uri="http://127.0.0.1:5000")
