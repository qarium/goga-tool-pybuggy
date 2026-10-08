"""Contract and logic tests for the ``apply.py`` migration entities."""

import inspect
import logging
import re
import tempfile
from pathlib import Path
from unittest import mock

import psycopg
import pytest
from git import Actor, Repo
from git.exc import GitCommandError
from goga_tool_pybuggy.sandbox.migrations import MigrationError, MigrationFile, apply_migrations, run_migrations
from psycopg import Connection

from .conftest import FailingAfterFirstConnection, FailingConnection, FakeConnection

APPLY_LOGGER = "goga_tool_pybuggy.sandbox.migrations.apply"
CLONE_FROM = "goga_tool_pybuggy.sandbox.migrations.apply.Repo.clone_from"

AUTHOR = Actor("pybuggy", "pybuggy@example.com")


def migration(filename: str, statements: list[str], no_transaction: bool = False) -> MigrationFile:
    """Build one apply-ready migration of the given shape.

    Args:
        filename: The source file name — carried into records and error messages.
        statements: The statement bodies, in apply order.
        no_transaction: Whether the file runs statement-by-statement in autocommit.

    Returns:
        The parsed-shaped ``MigrationFile``.
    """
    version = int(filename.split("_", 1)[0])

    return MigrationFile(version=version, filename=filename, statements=statements, no_transaction=no_transaction)


def write_clone_side_effect(relative: str = "db/migrations", statement: str = "CREATE TABLE t (id int)") -> object:
    """Build a clone double writing one valid migration set into the received target.

    Args:
        relative: The migrations folder to create inside the clone target.
        statement: The Up-section statement of the written ``00001_init.sql``.

    Returns:
        The ``Repo.clone_from`` side effect — a function creating the folder and the file
        under the target it receives.
    """

    def _clone(url: str, target: str, depth: int = 0, branch: str | None = None) -> None:
        folder = Path(target) / relative
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "00001_init.sql").write_text(f"-- +goose Up\n{statement};", encoding="utf-8")

    return _clone


class TestApplyContract:
    """Declared API of the migrations execution plane."""

    def test_both_names_are_importable_from_the_migrations_facade(self):
        """``apply_migrations`` and ``run_migrations`` are re-exported by the facade."""
        assert apply_migrations is not None
        assert run_migrations is not None

    def test_apply_migrations_signature_matches_the_contract(self):
        """``apply_migrations`` accepts ``conn: Connection, migrations: list[MigrationFile]``."""
        signature = inspect.signature(apply_migrations)
        parameters = list(signature.parameters.values())

        assert [parameter.name for parameter in parameters] == ["conn", "migrations"]
        assert parameters[0].annotation is Connection
        assert parameters[1].annotation == list[MigrationFile]

    def test_run_migrations_signature_matches_the_contract(self):
        """``run_migrations`` accepts ``conn, location, git_url, git_ref`` with the declared types."""
        signature = inspect.signature(run_migrations)
        parameters = list(signature.parameters.values())

        assert [parameter.name for parameter in parameters] == ["conn", "location", "git_url", "git_ref"]
        assert parameters[0].annotation is Connection
        assert parameters[1].annotation is str
        assert parameters[2].annotation == (str | None)
        assert parameters[3].annotation == (str | None)

    def test_the_facade_all_holds_exactly_the_eight_contract_names(self):
        """The cell facade completes at exactly the eight contract names."""
        import goga_tool_pybuggy.sandbox.migrations as migrations_cell

        assert migrations_cell.__all__ == [
            "MigrationError",
            "MigrationFile",
            "apply_migrations",
            "check_git_url",
            "check_local_migrations",
            "load_migration_set",
            "parse_migration_file",
            "run_migrations",
        ]


class TestApplyMigrations:
    """Logic of ``apply_migrations`` — the execution plane over the fake connection."""

    def test_apply_executes_each_file_in_its_own_transaction(self):
        """Two default migrations apply as one begin/commit pair per file, statements in order."""
        fake = FakeConnection()
        migrations = [
            migration("00001_init.sql", ["CREATE TABLE t (id int)"]),
            migration("00002_seed.sql", ["INSERT INTO t VALUES (1)", "INSERT INTO t VALUES (2)"]),
        ]

        apply_migrations(conn=fake, migrations=migrations)

        assert fake.statements == [
            ("transaction", "begin", None),
            ("execute", "CREATE TABLE t (id int)", None),
            ("transaction", "commit", None),
            ("transaction", "begin", None),
            ("execute", "INSERT INTO t VALUES (1)", None),
            ("execute", "INSERT INTO t VALUES (2)", None),
            ("transaction", "commit", None),
        ]

    def test_apply_no_transaction_runs_statement_by_statement(self):
        """A NO TRANSACTION file executes directly on the autocommit connection — no transaction markers."""
        fake = FakeConnection()
        migrations = [migration("00003_index.sql", ["CREATE INDEX CONCURRENTLY i ON t (c)"], no_transaction=True)]

        apply_migrations(conn=fake, migrations=migrations)

        assert fake.statements == [("execute", "CREATE INDEX CONCURRENTLY i ON t (c)", None)]

    def test_apply_logs_one_progress_line_per_file(self, caplog: pytest.LogCaptureFixture):
        """Each applied file reports one structured INFO line, in application order."""
        fake = FakeConnection()
        migrations = [
            migration("00001_init.sql", ["SELECT 1"]),
            migration("00002_seed.sql", ["SELECT 2"]),
        ]

        with caplog.at_level(logging.INFO, logger=APPLY_LOGGER):
            apply_migrations(conn=fake, migrations=migrations)

        records = [record for record in caplog.records if record.message == "migration applied"]

        assert [record.migration for record in records] == ["00001_init.sql", "00002_seed.sql"]
        assert [record.version for record in records] == [1, 2]

    def test_apply_failure_names_file_and_server_message_and_stops(self):
        """The first failed statement wraps into ``MigrationError`` and stops the apply.

        The message names the file and the server text; the earlier empty file commits
        vacuously; the failing default file rolls back fully; the later file never runs.
        """
        fake = FailingConnection()
        migrations = [
            migration("00001_empty.sql", []),
            migration("00002_bad.sql", ["INSERT INTO ghost VALUES (1)"]),
            migration("00003_after.sql", ["SELECT 3"]),
        ]

        with pytest.raises(MigrationError) as excinfo:
            apply_migrations(conn=fake, migrations=migrations)

        assert "00002_bad.sql" in str(excinfo.value)
        assert 'relation "ghost" does not exist' in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, psycopg.Error)
        assert fake.statements == [
            ("transaction", "begin", None),
            ("transaction", "commit", None),
            ("transaction", "begin", None),
            ("transaction", "rollback", None),
        ]

    def test_apply_no_transaction_failure_keeps_applied_statements(self):
        """A failed NO TRANSACTION statement stops the apply; the earlier statements stay applied.

        The error names the file and the server message; no transaction markers appear —
        the file runs statement-by-statement in autocommit, so nothing rolls back.
        """
        fake = FailingAfterFirstConnection()
        migrations = [
            migration(
                "00005_seed.sql",
                ["INSERT INTO t VALUES (1)", "INSERT INTO ghost VALUES (2)"],
                no_transaction=True,
            )
        ]

        with pytest.raises(MigrationError) as excinfo:
            apply_migrations(conn=fake, migrations=migrations)

        assert "00005_seed.sql" in str(excinfo.value)
        assert 'relation "ghost" does not exist' in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, psycopg.Error)
        assert fake.statements == [("execute", "INSERT INTO t VALUES (1)", None)]

    def test_apply_empty_set_is_noop(self):
        """An empty set executes nothing and raises nothing."""
        fake = FakeConnection()

        apply_migrations(conn=fake, migrations=[])

        assert fake.statements == []

    def test_apply_empty_statements_file_commits_vacuously_and_logs(self, caplog: pytest.LogCaptureFixture):
        """A statement-less default file commits vacuously and still reports its progress line."""
        fake = FakeConnection()
        migrations = [migration("00009_empty.sql", [])]

        with caplog.at_level(logging.INFO, logger=APPLY_LOGGER):
            apply_migrations(conn=fake, migrations=migrations)

        assert fake.statements == [
            ("transaction", "begin", None),
            ("transaction", "commit", None),
        ]

        records = [record for record in caplog.records if record.message == "migration applied"]
        assert [record.migration for record in records] == ["00009_empty.sql"]


class TestRunMigrations:
    """Logic of ``run_migrations`` — source resolution and one orchestration per call."""

    def test_run_local_source_resolves_against_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ):
        """A local source resolves against the current working directory; the clone API is never touched."""
        monkeypatch.chdir(tmp_path)
        folder = tmp_path / "db" / "migrations"
        folder.mkdir(parents=True)
        (folder / "00001_init.sql").write_text("-- +goose Up\nCREATE TABLE t (id int);", encoding="utf-8")

        fake = FakeConnection()

        with caplog.at_level(logging.DEBUG, logger=APPLY_LOGGER), mock.patch(CLONE_FROM) as clone:
            run_migrations(conn=fake, location="db/migrations", git_url=None, git_ref=None)

        clone.assert_not_called()
        assert fake.statements[0] == ("transaction", "begin", None)
        assert ("execute", "CREATE TABLE t (id int)", None) in fake.statements

        records = [record for record in caplog.records if record.message == "migrations source resolved"]
        assert [record.location for record in records] == [str(folder)]

    def test_run_local_source_absolute_location_overrides_cwd(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """An absolute ``location`` overrides the cwd anchor — the declared folder applies as given."""
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)
        folder = tmp_path / "db" / "migrations"
        folder.mkdir(parents=True)
        (folder / "00001_init.sql").write_text("-- +goose Up\nSELECT 1;", encoding="utf-8")

        fake = FakeConnection()

        run_migrations(conn=fake, location=str(folder), git_url=None, git_ref=None)

        assert ("execute", "SELECT 1", None) in fake.statements

    def test_run_remote_source_clones_a_local_repository(self, tmp_path: Path):
        """A real shallow clone of a local ``file://`` repository applies the committed set.

        The GitPython seam runs end to end — no clone double: the committed migration file
        loads from the clone and applies, and the clone target is deleted afterwards.
        """
        source = tmp_path / "service"
        (source / "db" / "migrations").mkdir(parents=True)
        (source / "db" / "migrations" / "00001_init.sql").write_text("-- +goose Up\nSELECT 1;", encoding="utf-8")

        repo = Repo.init(source)
        repo.index.add(["db/migrations/00001_init.sql"])
        repo.index.commit("init", author=AUTHOR, committer=AUTHOR)

        fake = FakeConnection()

        run_migrations(conn=fake, location="db/migrations", git_url=f"file://{source}", git_ref=None)

        assert ("execute", "SELECT 1", None) in fake.statements

    def test_run_remote_source_clones_and_applies(self):
        """A remote source shallow-clones into a fresh temp target and applies the cloned set.

        The clone call carries the url, the temp target, ``depth=1`` and the declared
        branch; the target no longer exists after the call — the clone is deleted on every
        exit path.
        """
        fake = FakeConnection()

        with mock.patch(CLONE_FROM, side_effect=write_clone_side_effect()) as clone:
            run_migrations(
                conn=fake,
                location="db/migrations",
                git_url="https://gitlab.example/acme/service.git",
                git_ref="release-branch",
            )

        clone.assert_called_once()
        args, kwargs = clone.call_args
        assert args[0] == "https://gitlab.example/acme/service.git"
        assert kwargs == {"depth": 1, "branch": "release-branch"}

        target = Path(args[1])
        assert "pybuggy-migrations-" in target.name
        assert not target.exists()
        assert ("execute", "CREATE TABLE t (id int)", None) in fake.statements

    def test_run_remote_source_clones_default_branch_without_ref(self):
        """``git_ref`` None passes ``branch=None`` — GitPython omits ``--branch``."""
        fake = FakeConnection()

        with mock.patch(CLONE_FROM, side_effect=write_clone_side_effect(statement="SELECT 1")) as clone:
            run_migrations(
                conn=fake, location="db/migrations", git_url="https://gitlab.example/acme/s.git", git_ref=None
            )

        assert clone.call_args.kwargs["branch"] is None
        assert ("execute", "SELECT 1", None) in fake.statements

    def test_run_local_source_missing_folder(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """A local source without the declared folder raises naming the location; nothing executes."""
        monkeypatch.chdir(tmp_path)
        fake = FakeConnection()

        with pytest.raises(MigrationError, match=re.escape("db/migrations")):
            run_migrations(conn=fake, location="db/migrations", git_url=None, git_ref=None)

        assert fake.statements == []

    def test_run_remote_source_clone_failure(self):
        """A failed clone wraps into ``MigrationError`` naming the URL; the cause chain stays intact.

        The temporary clone target is deleted even on the failed exit path.
        """
        fake = FakeConnection()

        with (
            mock.patch(
                CLONE_FROM,
                side_effect=GitCommandError("clone", 128, b"fatal: Authentication failed"),
            ) as clone,
            pytest.raises(MigrationError, match=r"failed to clone https://gitlab\.example/acme/s\.git") as excinfo,
        ):
            run_migrations(
                conn=fake, location="db/migrations", git_url="https://gitlab.example/acme/s.git", git_ref=None
            )

        assert "fatal: Authentication failed" in str(excinfo.value)
        assert isinstance(excinfo.value.__cause__, GitCommandError)

        target = Path(clone.call_args.args[1])
        assert not target.exists()
        assert fake.statements == []

    def test_run_remote_source_missing_location_in_clone(self):
        """A declared location absent from the clone raises naming the resolved path."""
        fake = FakeConnection()

        def clone_bare_root(url: str, target: str, depth: int = 0, branch: str | None = None) -> None:
            Path(target).mkdir(parents=True, exist_ok=True)

        with (
            mock.patch(CLONE_FROM, side_effect=clone_bare_root),
            pytest.raises(
                MigrationError,
                match=rf"{re.escape('db/migrations')}.*the migrations folder is missing in the cloned repository",
            ),
        ):
            run_migrations(
                conn=fake, location="db/migrations", git_url="https://gitlab.example/acme/s.git", git_ref=None
            )

        assert fake.statements == []

    def test_run_remote_source_location_escapes_clone(self):
        """A location resolving outside the clone root raises naming the location; nothing executes."""
        fake = FakeConnection()

        def clone_bare_root(url: str, target: str, depth: int = 0, branch: str | None = None) -> None:
            Path(target).mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory() as escape_root:
            escape = Path(escape_root) / "migrations"
            escape.mkdir()
            (escape / "00001_init.sql").write_text("-- +goose Up\nSELECT 1;", encoding="utf-8")

            location = f"../{Path(escape_root).name}/migrations"

            with (
                mock.patch(CLONE_FROM, side_effect=clone_bare_root),
                pytest.raises(MigrationError, match=rf"{re.escape(location)}.*escapes the clone"),
            ):
                run_migrations(conn=fake, location=location, git_url="https://gitlab.example/acme/s.git", git_ref=None)

        assert fake.statements == []
