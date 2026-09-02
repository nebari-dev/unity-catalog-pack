import json
import subprocess
import tempfile
from pathlib import Path

import pytest
import yaml

CHART = Path(__file__).resolve().parents[2] / "chart"
RELEASE = "unity-catalog"


def _helm_template(values: dict | None, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    args = ["helm", "template", RELEASE, str(CHART), "--namespace", "unity-catalog"]
    if values:
        f = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
        json.dump(values, f)
        f.close()
        args += ["-f", f.name]
    args += extra_args or []
    return subprocess.run(args, capture_output=True, text=True)


def render(values: dict | None = None, extra_args: list[str] | None = None) -> list[dict]:
    proc = _helm_template(values, extra_args)
    assert proc.returncode == 0, proc.stderr
    return [d for d in yaml.safe_load_all(proc.stdout) if d]


def render_error(values: dict) -> str:
    proc = _helm_template(values)
    assert proc.returncode != 0, "expected helm template to fail"
    return proc.stderr


def find(docs: list[dict], kind: str, name: str | None = None) -> dict | None:
    for d in docs:
        if d.get("kind") == kind and (name is None or d["metadata"]["name"] == name):
            return d
    return None


def find_all(docs: list[dict], kind: str) -> list[dict]:
    return [d for d in docs if d.get("kind") == kind]


@pytest.fixture(scope="session")
def standalone_docs() -> list[dict]:
    return render()
