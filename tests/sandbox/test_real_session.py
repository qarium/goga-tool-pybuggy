"""A real pytest session with the sandbox plugin installed — the install-to-fixture wiring end to end.

The unit suites drive the plugin fixtures on hand-rolled request doubles; this module runs
one real pytest session in a scratch consumer repository instead: a conftest that stubs the
container seams, installs the plugins through ``plugin.install()``, and a test module mixing a
sandbox-free ``api`` test with sandbox tests. The run verifies the integration points only a
real session exercises — the product ``sandbox`` fixture registered from the plugin (an
unknown fixture would fail the run), the marker registered pre-collection (an unknown mark
would fail the run under ``-W error::pytest.PytestUnknownMarkWarning``), the lazy start (no
container before the first sandbox-needing test), the per-test product reset between sandbox
tests, the ``@services`` decorator pulling the sandbox into a test's fixture closure, and the
explicit api address binding through ``api.bind(sandbox)`` — plus the start/stop ordering
recorded by the stubs.
"""

import json
import os
import pathlib
import subprocess
import sys

DOCUMENT = """\
instance:
  image: my-service:latest
  port: 8080
  env:
    DATABASE_URL: "postgres://{{db.host}}:{{db.port}}/test"
services:
  db:
    kind: postgresql
"""

CONFTEST = """\
import json
import pathlib

from goga_tool_pybuggy.sandbox import sandbox as sandbox_module
from goga_tool_pybuggy.sandbox.engines import InstanceAddress

RECORD = pathlib.Path(__file__).parent / "events.jsonl"


def record(event):
    with RECORD.open("a", encoding="utf-8") as sink:
        sink.write(json.dumps({"event": event}) + "\\n")


class StubEngine:
    def __init__(self, name, kind):
        self.name = name
        self.kind = kind
        self.applied = []
        self.journaled = []
        self.started = False

    @property
    def address(self):
        return InstanceAddress(host="127.0.0.2", port=5432)

    def start(self, startup, network=None):
        record(f"engine:{self.name}:start")
        self.started = True
        self.journaled.extend(startup)

    def apply(self, operations):
        self.applied.extend(operations)

    def record(self, operations):
        self.journaled.extend(operations)

    def reset(self):
        record(f"engine:{self.name}:reset")

    def stop(self):
        record(f"engine:{self.name}:stop")


class StubService:
    host = "127.0.0.9"
    port = 9000

    def start(self, env, network=None):
        record("instance:start")
        record("instance-env:" + env["DATABASE_URL"])

    def stop(self):
        record("instance:stop")

    def alive(self):
        return True

    def logs(self):
        return ""


class StubNetwork:
    def __init__(self, *args, **kwargs):
        pass

    def create(self):
        record("network:create")
        return self

    def remove(self):
        record("network:remove")


sandbox_module.build_engine = lambda service_config: StubEngine(service_config.name, service_config.kind)
sandbox_module.ServiceContainer = lambda instance_config: StubService()
sandbox_module.check_runtime = lambda: record("runtime-check")
sandbox_module.Network = StubNetwork

from goga_tool_pybuggy import plugin  # noqa: E402

plugin.install()
"""

TESTS = """\
import pathlib

from goga_tool_pybuggy import services

RECORD = pathlib.Path(__file__).parent / "events.jsonl"


def record(event):
    with RECORD.open("a", encoding="utf-8") as sink:
        sink.write(event + "\\n")


def test_static_api_without_the_sandbox(api):
    record("test:static-api-body")
    assert api.base_url == "http://static-target"


@services(postgresql={"db": [{"table": "customers", "rows": [{"id": 1, "name": "Ann"}]}]})
def test_preset_applies_ahead_of_the_test_operations(sandbox):
    record("test:preset-body")
    sandbox.postgresql("db").insert("orders", [{"id": 2}])
    sandbox.apply_pending()

    engine = sandbox.engines["db"]
    assert [op.payload["table"] for op in engine.applied] == ["customers", "orders"]


@services(postgresql={"db": [{"table": "customers", "rows": [{"id": 9}]}]})
def test_bound_api_points_at_the_sandbox(api, sandbox):
    record("test:api-body")
    api.bind(sandbox)
    assert api.base_url == "http://127.0.0.9:9000"
"""

SANDBOXLESS_TESTS = """\
def test_needs_the_sandbox(sandbox):
    assert sandbox is not None
"""


def run_real_session(project: pathlib.Path) -> subprocess.CompletedProcess[str]:
    """Run one real pytest session inside the scratch consumer repository.

    Args:
        project: The scratch repository root carrying the document, conftest and tests.

    Returns:
        The completed pytest subprocess — returncode and captured output.
    """
    env = dict(os.environ)
    env.update(
        {
            "BASE_URL": "http://static-target",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTEST_ADDOPTS": "",
        }
    )

    return subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            "-W",
            "error::pytest.PytestUnknownMarkWarning",
        ],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def read_events(project: pathlib.Path) -> list[str]:
    """Read the stub-recorded event sequence of one finished session.

    Args:
        project: The scratch repository root carrying ``events.jsonl``.

    Returns:
        The recorded events, in recording order.
    """
    events: list[str] = []

    for line in (project / "events.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            events.append(json.loads(line)["event"])
        except json.JSONDecodeError:
            events.append(line)

    return events


def test_installed_plugin_runs_a_real_pytest_session(tmp_path: pathlib.Path):
    """The installed sandbox plugin drives one real session: fixture, marker, lazy start, reset.

    The session must pass with the marker escalated to an error on first unknown use; the
    static api test must run before any container (the lazy start), its address the rendered
    base_url; the first sandbox test must bring the topology up ahead of its body and see the
    preset applied ahead of its own operations; the product reset must run between the sandbox
    tests; the ``@services``-marked api test must reach the sandbox address through the explicit
    ``api.bind(sandbox)``; and the stub lifecycle must show the network created before the
    engines and removed after every container stopped.
    """
    document = tmp_path / ".goga" / "tools" / "pybuggy" / "sandbox.yml"
    document.parent.mkdir(parents=True)
    document.write_text(DOCUMENT, encoding="utf-8")

    (tmp_path / "conftest.py").write_text(CONFTEST, encoding="utf-8")
    (tmp_path / "test_sample.py").write_text(TESTS, encoding="utf-8")

    result = run_real_session(tmp_path)

    assert result.returncode == 0, f"the real session failed:\n{result.stdout}\n{result.stderr}"
    assert "3 passed" in result.stdout

    events = read_events(tmp_path)

    assert events[0] == "test:static-api-body"
    assert events.index("test:static-api-body") < events.index("runtime-check")
    assert events.index("runtime-check") < events.index("network:create")
    assert events.index("network:create") < events.index("engine:db:start")
    assert "instance-env:postgres://127.0.0.2:5432/test" in events
    assert events.index("engine:db:start") < events.index("test:preset-body")
    assert events.count("engine:db:reset") == 2
    first_reset = events.index("engine:db:reset")
    assert first_reset < events.index("test:preset-body")
    second_reset = events.index("engine:db:reset", first_reset + 1)
    assert events.index("test:preset-body") < second_reset < events.index("test:api-body")
    assert events.index("test:api-body") < events.index("instance:stop")
    assert events.index("instance:stop") < events.index("engine:db:stop")
    assert events[-1] == "network:remove"


def test_sandbox_fixture_is_absent_without_the_document(tmp_path: pathlib.Path):
    """Without the document no sandbox plugin is installed — the fixture does not exist and a
    test requesting it fails with pytest's standard error."""
    (tmp_path / "conftest.py").write_text(CONFTEST, encoding="utf-8")
    (tmp_path / "test_sample.py").write_text(SANDBOXLESS_TESTS, encoding="utf-8")

    result = run_real_session(tmp_path)

    assert result.returncode != 0
    assert "fixture 'sandbox' not found" in result.stdout
