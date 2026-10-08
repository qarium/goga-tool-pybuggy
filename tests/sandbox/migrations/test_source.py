"""Contract and logic tests for the ``source.py`` migration entities."""

import inspect
import re
from pathlib import Path

import pytest
from goga_tool_pybuggy.sandbox.migrations import MigrationError, check_git_url, check_local_migrations


class TestSourceContract:
    """Declared API of the migrations source shape checks."""

    def test_both_names_are_importable_from_the_migrations_facade(self):
        """``check_local_migrations`` and ``check_git_url`` are re-exported by the facade."""
        assert check_local_migrations is not None
        assert check_git_url is not None

    def test_check_local_migrations_signature_matches_the_contract(self):
        """``check_local_migrations`` accepts ``folder: Path``."""
        signature = inspect.signature(check_local_migrations)
        parameters = list(signature.parameters.values())

        assert [parameter.name for parameter in parameters] == ["folder"]
        assert parameters[0].annotation is Path

    def test_check_git_url_signature_matches_the_contract(self):
        """``check_git_url`` accepts ``url: str``."""
        signature = inspect.signature(check_git_url)
        parameters = list(signature.parameters.values())

        assert [parameter.name for parameter in parameters] == ["url"]
        assert parameters[0].annotation is str


class TestCheckLocalMigrations:
    """Logic of ``check_local_migrations``."""

    def test_check_local_migrations_with_valid_folder(self, tmp_path):
        """A folder of grammatical unique-versioned `.sql` files raises no exception."""
        folder = tmp_path / "db" / "migrations"
        folder.mkdir(parents=True)
        (folder / "00001_init.sql").write_text("-- +goose Up\nSELECT 1;")
        (folder / "00002_add_users.sql").write_text("-- +goose Up\nSELECT 2;")

        assert check_local_migrations(folder) is None

    def test_check_local_migrations_ignores_non_sql_files(self, tmp_path):
        """Non-`.sql` entries beside valid migrations never fail the check."""
        folder = tmp_path / "db" / "migrations"
        folder.mkdir(parents=True)
        (folder / "00001_init.sql").write_text("-- +goose Up\nSELECT 1;")
        (folder / "notes.txt").write_text("scratch")
        (folder / "README.md").write_text("# migrations")

        assert check_local_migrations(folder) is None

    def test_check_local_migrations_with_missing_folder(self, tmp_path):
        """A folder that does not exist raises naming the path."""
        missing = tmp_path / "db" / "migrations"

        with pytest.raises(MigrationError, match=re.escape(str(missing))):
            check_local_migrations(missing)

    def test_check_local_migrations_with_file_instead_of_folder(self, tmp_path):
        """A plain file at the declared location raises naming the path."""
        location = tmp_path / "migrations"
        location.write_text("not a folder")

        with pytest.raises(MigrationError, match=re.escape(str(location))):
            check_local_migrations(location)

    def test_check_local_migrations_with_empty_folder(self, tmp_path):
        """An existing but empty folder raises naming the folder and the emptiness rule."""
        folder = tmp_path / "empty"
        folder.mkdir()

        with pytest.raises(MigrationError, match=rf"{re.escape(str(folder))}.*the migrations folder is empty"):
            check_local_migrations(folder)

    def test_check_local_migrations_without_sql_files(self, tmp_path):
        """A folder holding only non-`.sql` entries raises naming the no-`.sql` rule."""
        folder = tmp_path / "onlytxt"
        folder.mkdir()
        (folder / "notes.txt").write_text("scratch")
        (folder / "README.md").write_text("# migrations")

        with pytest.raises(
            MigrationError,
            match=rf"{re.escape(str(folder))}.*the migrations folder holds no \.sql files",
        ):
            check_local_migrations(folder)

    def test_check_local_migrations_with_invalid_filename(self, tmp_path):
        """A non-grammatical `.sql` name beside a valid one raises naming folder and file."""
        folder = tmp_path / "db" / "migrations"
        folder.mkdir(parents=True)
        (folder / "00001_init.sql").write_text("-- +goose Up\nSELECT 1;")
        (folder / "create_orders.sql").write_text("-- +goose Up\nSELECT 2;")

        with pytest.raises(
            MigrationError,
            match=rf"{re.escape(str(folder))}.*{re.escape('create_orders.sql')}.*expected <version>_<description>\.sql",
        ):
            check_local_migrations(folder)

    def test_check_local_migrations_with_duplicate_versions(self, tmp_path):
        """Zero-padded and bare prefixes of the same integer raise naming both files and the version."""
        folder = tmp_path / "db" / "migrations"
        folder.mkdir(parents=True)
        (folder / "00001_a.sql").write_text("-- +goose Up\nSELECT 1;")
        (folder / "1_b.sql").write_text("-- +goose Up\nSELECT 2;")

        expected = rf"{re.escape(str(folder))}.*duplicate migration version 1.*00001_a\.sql and 1_b\.sql"

        with pytest.raises(MigrationError, match=expected):
            check_local_migrations(folder)


class TestCheckGitUrl:
    """Logic of ``check_git_url``."""

    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com/acme/service.git",
            "http://github.com/acme/service.git",
            "git://github.com/acme/service.git",
            "ssh://git@github.com/acme/service.git",
        ],
    )
    def test_check_git_url_accepts_allowed_schemes(self, url):
        """Each of the four allowed schemes passes — an ssh username is not a credential."""
        assert check_git_url(url) is None

    @pytest.mark.parametrize(
        "url",
        [
            "ftp://host/repo.git",
            "file:///etc/passwd",
            "git@github.com:acme/service.git",
        ],
    )
    def test_check_git_url_rejects_unknown_scheme(self, url):
        """A scheme outside the allowlist raises naming the URL — scp-style included (decision A)."""
        with pytest.raises(MigrationError, match=rf"{re.escape(url)}.*disallowed git URL scheme"):
            check_git_url(url)

    @pytest.mark.parametrize(
        "url",
        [
            "https://user:token@host/repo.git",
            "https://user@host/repo.git",
        ],
    )
    def test_check_git_url_rejects_embedded_credentials(self, url):
        """A user or user:password in the netloc raises naming the URL and the credentials rule."""
        with pytest.raises(MigrationError, match=rf"{re.escape(url)}.*must not embed credentials"):
            check_git_url(url)
