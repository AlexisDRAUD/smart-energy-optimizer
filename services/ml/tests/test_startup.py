import importlib.util
import signal
from contextlib import nullcontext
from pathlib import Path
from urllib.error import URLError

import pytest

spec = importlib.util.spec_from_file_location("startup", Path(__file__).parents[1] / "start.py")
startup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(startup)


class Process:
    def __init__(self, code=None):
        self.pid = 123456
        self.returncode = code

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode or 0


@pytest.fixture
def supervisor(monkeypatch):
    commands, killed = [], []
    monkeypatch.setattr(startup.Path, "mkdir", lambda *a, **kw: None)
    monkeypatch.setattr(startup.signal, "signal", lambda *a: None)
    monkeypatch.setattr(startup.os, "killpg", lambda *args: killed.append(args))
    monkeypatch.setattr(startup, "urlopen", lambda *a, **kw: nullcontext())
    monkeypatch.setenv("ML_TRAIN_ON_START", "1")
    monkeypatch.setenv("TRAIN_ARGS", "")
    monkeypatch.setenv("MLFLOW_START_TIMEOUT_SECONDS", "2")

    def install(*processes):
        remaining = iter(processes)

        def spawn(command, **kwargs):
            assert kwargs["start_new_session"]
            commands.append(command)
            return next(remaining)

        monkeypatch.setattr(startup.subprocess, "Popen", spawn)

    return install, commands, killed


def test_training_failure_is_fatal(supervisor):
    install, commands, killed = supervisor
    install(Process(), Process(7))
    assert startup.main() == 7
    assert commands[1][-1] == "/app/main.py"
    assert len(killed) == 2


def test_server_only_and_persistent_proxy(supervisor, monkeypatch):
    install, commands, _ = supervisor
    install(Process())
    monkeypatch.setenv("ML_TRAIN_ON_START", "0")
    assert startup.main() == 0
    assert len(commands) == 1
    assert "sqlite:////mlflow/mlflow.db" in commands[0]
    assert "mlflow-artifacts:/" in commands[0]
    assert "--app-name" in commands[0]
    assert "--gunicorn-opts" not in commands[0]
    assert "--allowed-hosts" in commands[0]


def test_readiness_timeout_stops_server(supervisor, monkeypatch):
    install, _, killed = supervisor
    install(Process())

    def unavailable(*args, **kwargs):
        raise URLError("not ready")

    clock = iter([0, 3, 4, 4])
    monkeypatch.setattr(startup, "urlopen", unavailable)
    monkeypatch.setattr(startup.time, "monotonic", lambda: next(clock))
    with pytest.raises(RuntimeError, match="deadline"):
        startup.main()
    assert killed == [(123456, signal.SIGTERM)]


def test_server_exit_before_training(supervisor):
    install, commands, killed = supervisor
    install(Process(5))
    assert startup.main() == 5
    assert len(commands) == len(killed) == 1
