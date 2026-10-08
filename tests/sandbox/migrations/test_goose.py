"""Contract and logic tests for the ``goose.py`` and ``errors.py`` migration entities."""

import inspect
import re
from pathlib import Path

import pytest
from goga_tool_pybuggy.sandbox.migrations import MigrationError, MigrationFile, load_migration_set, parse_migration_file
from pydantic import BaseModel


class TestGooseContract:
    """Declared API of the migrations cell core."""

    def test_all_four_names_are_importable_from_the_migrations_facade(self):
        """The four Task 2 names are re-exported by the migrations facade."""
        assert MigrationError is not None
        assert MigrationFile is not None
        assert parse_migration_file is not None
        assert load_migration_set is not None

    def test_migration_error_subclasses_runtime_error(self):
        """``MigrationError`` is the ``RuntimeError`` subtype of the migrations domain."""
        assert issubclass(MigrationError, RuntimeError)

    def test_migration_file_is_a_pydantic_model(self):
        """``MigrationFile`` subclasses ``pydantic.BaseModel``."""
        assert issubclass(MigrationFile, BaseModel)

    def test_migration_file_constructor_is_kw_only(self):
        """All constructor parameters of ``MigrationFile`` are keyword-only."""
        signature = inspect.signature(MigrationFile)

        for parameter in signature.parameters.values():
            assert parameter.kind is inspect.Parameter.KEYWORD_ONLY

    def test_migration_file_declares_the_contract_fields(self):
        """The model declares the ``version``, ``filename``, ``statements`` and ``no_transaction`` fields."""
        assert set(MigrationFile.model_fields) == {"version", "filename", "statements", "no_transaction"}

    def test_migration_file_properties_return_declared_types(self):
        """Construction with sample data exposes the declared property types."""
        migration = MigrationFile(version=1, filename="00001_init.sql", statements=["SELECT 1"], no_transaction=False)

        assert isinstance(migration.version, int)
        assert isinstance(migration.filename, str)
        assert isinstance(migration.statements, list)
        assert all(isinstance(statement, str) for statement in migration.statements)
        assert isinstance(migration.no_transaction, bool)

    def test_parse_migration_file_signature_matches_the_contract(self):
        """``parse_migration_file`` accepts ``filename: str, text: str``."""
        signature = inspect.signature(parse_migration_file)
        parameters = list(signature.parameters.values())

        assert [parameter.name for parameter in parameters] == ["filename", "text"]
        assert parameters[0].annotation is str
        assert parameters[1].annotation is str

    def test_load_migration_set_signature_matches_the_contract(self):
        """``load_migration_set`` accepts ``folder: Path``."""
        signature = inspect.signature(load_migration_set)
        parameters = list(signature.parameters.values())

        assert [parameter.name for parameter in parameters] == ["folder"]
        assert parameters[0].annotation is Path


class TestParseMigrationFile:
    """Logic of ``parse_migration_file`` — positive scenarios."""

    def test_parse_simple_up_statements(self):
        """The canonical goose file parses into the two Up statements without terminating semicolons."""
        text = "\n".join(
            [
                "-- +goose Up",
                "CREATE TABLE orders (id serial PRIMARY KEY, customer int);",
                "CREATE INDEX idx_orders_customer ON orders (customer);",
                "",
                "-- +goose Down",
                "DROP INDEX idx_orders_customer;",
                "DROP TABLE orders;",
            ]
        )

        migration = parse_migration_file("00003_create_orders.sql", text)

        assert migration.version == 3
        assert migration.filename == "00003_create_orders.sql"
        assert migration.no_transaction is False
        assert migration.statements == [
            "CREATE TABLE orders (id serial PRIMARY KEY, customer int)",
            "CREATE INDEX idx_orders_customer ON orders (customer)",
        ]

    def test_parse_statement_begin_body_preserves_interior_semicolons(self):
        """A StatementBegin/End body stays one verbatim statement; interior semicolons never split it."""
        text = "\n".join(
            [
                "-- +goose Up",
                "-- +goose StatementBegin",
                "CREATE OR REPLACE FUNCTION audit_orders() RETURNS trigger AS $$",
                "BEGIN",
                "  INSERT INTO audit_log (order_id) VALUES (NEW.id);",
                "  RETURN NEW;",
                "END;",
                "$$ LANGUAGE plpgsql;",
                "-- +goose StatementEnd",
                "CREATE INDEX idx_orders_customer ON orders (customer);",
            ]
        )

        migration = parse_migration_file("00002_audit.sql", text)

        assert len(migration.statements) == 2
        assert "RETURN NEW;" in migration.statements[0]
        assert "$$ LANGUAGE plpgsql;" in migration.statements[0]
        assert migration.statements[1] == "CREATE INDEX idx_orders_customer ON orders (customer)"

    def test_parse_preserves_file_order_of_fragments_and_bodies(self):
        """Plain statements and bodies interleave in exactly the file order (the R1 regression pin)."""
        text = "\n".join(
            [
                "-- +goose Up",
                "CREATE TABLE t (id int);",
                "-- +goose StatementBegin",
                "CREATE FUNCTION f() RETURNS int AS $$",
                "BEGIN",
                "  RETURN 1;",
                "END;",
                "$$ LANGUAGE plpgsql;",
                "-- +goose StatementEnd",
                "CREATE INDEX i ON t (id);",
            ]
        )

        migration = parse_migration_file("00001_mixed.sql", text)

        assert len(migration.statements) == 3
        assert migration.statements[0] == "CREATE TABLE t (id int)"
        assert "CREATE FUNCTION f()" in migration.statements[1]
        assert "RETURN 1;" in migration.statements[1]
        assert migration.statements[2] == "CREATE INDEX i ON t (id)"

    def test_parse_no_transaction_flag(self):
        """``-- +goose NO TRANSACTION`` before Up sets the flag; the statements still parse."""
        text = "\n".join(
            [
                "-- +goose NO TRANSACTION",
                "-- +goose Up",
                "CREATE INDEX CONCURRENTLY idx ON t (c);",
            ]
        )

        migration = parse_migration_file("00004_concurrent.sql", text)

        assert migration.no_transaction is True
        assert migration.statements == ["CREATE INDEX CONCURRENTLY idx ON t (c)"]

    def test_parse_down_section_skipped(self):
        """Unsupported annotations and interpolation after Down never raise; only Up statements apply."""
        text = "\n".join(
            [
                "-- +goose Up",
                "SELECT 1;",
                "",
                "-- +goose Down",
                "-- +goose Env FOO",
                "SELECT {{.Var}};",
            ]
        )

        migration = parse_migration_file("00005_down.sql", text)

        assert migration.statements == ["SELECT 1"]

    def test_parse_extracts_timestamp_version(self):
        """A timestamp-style filename yields its full numeric version."""
        migration = parse_migration_file("20230102103456_init.sql", "-- +goose Up\nSELECT 1;")

        assert migration.version == 20230102103456

    def test_parse_empty_up_section(self):
        """An Up section immediately followed by Down parses to no statements."""
        migration = parse_migration_file("00009_empty.sql", "-- +goose Up\n-- +goose Down\nDROP TABLE t;")

        assert migration.version == 9
        assert migration.statements == []

    def test_parse_drops_comment_only_fragments(self):
        """Comment-only fragments are dropped; leading comments inside a kept piece stay in its text."""
        text = "\n".join(
            [
                "-- +goose Up",
                "-- leading comment about the table",
                "SELECT 1;",
                "-- trailing comment",
                "SELECT 2;",
                "-- dangling comment",
            ]
        )

        migration = parse_migration_file("00006_comments.sql", text)

        assert migration.statements == ["-- leading comment about the table\nSELECT 1", "-- trailing comment\nSELECT 2"]
        assert all(
            any(not line.strip().startswith("--") for line in statement.splitlines())
            for statement in migration.statements
        )

    def test_parse_crlf_file(self):
        """CRLF line endings parse into clean statement bodies without ``\\r``."""
        text = "-- +goose Up\r\nCREATE TABLE t (id int);\r\n"

        migration = parse_migration_file("00007_crlf.sql", text)

        assert migration.statements == ["CREATE TABLE t (id int)"]
        assert "\r" not in "".join(migration.statements)


class TestParseMigrationFileFailures:
    """Logic of ``parse_migration_file`` — failure scenarios."""

    def test_parse_without_up_section(self):
        """A file with header and Down only has no Up section and raises naming the file."""
        with pytest.raises(MigrationError, match=re.escape("00008_no_up.sql")) as excinfo:
            parse_migration_file("00008_no_up.sql", "-- +goose Down\nDROP TABLE t;")

        assert "Up" in str(excinfo.value)

    def test_parse_with_invalid_filename(self):
        """A filename without a valid version prefix raises naming the file."""
        with pytest.raises(MigrationError, match=re.escape("create_orders.sql")):
            parse_migration_file("create_orders.sql", "-- +goose Up\nSELECT 1;")

    def test_parse_with_unclosed_statement_begin(self):
        """A StatementBegin without a matching StatementEnd raises naming the file."""
        text = "\n".join(
            [
                "-- +goose Up",
                "-- +goose StatementBegin",
                "CREATE FUNCTION f() RETURNS int AS $$",
                "BEGIN",
                "  RETURN 1;",
                "END;",
            ]
        )

        with pytest.raises(MigrationError, match=re.escape("00010_unclosed.sql")):
            parse_migration_file("00010_unclosed.sql", text)

    def test_parse_with_statement_end_without_begin(self):
        """A stray StatementEnd inside the Up section raises naming the file."""
        text = "\n".join(["-- +goose Up", "SELECT 1;", "-- +goose StatementEnd"])

        with pytest.raises(MigrationError, match=re.escape("00011_stray.sql")):
            parse_migration_file("00011_stray.sql", text)

    @pytest.mark.parametrize("region", ["header", "up"])
    def test_parse_with_unknown_annotation(self, region):
        """An unsupported +goose annotation raises naming the file and the token, in either region."""
        if region == "header":
            text = "-- +goose Env FOO\n-- +goose Up\nSELECT 1;"
        else:
            text = "-- +goose Up\n-- +goose Env FOO\nSELECT 1;"

        with pytest.raises(MigrationError, match=re.escape("00012_env.sql")) as excinfo:
            parse_migration_file("00012_env.sql", text)

        assert "Env FOO" in str(excinfo.value)

    def test_parse_with_no_transaction_after_up(self):
        """``NO TRANSACTION`` declared after Up raises naming the file."""
        text = "\n".join(["-- +goose Up", "-- +goose NO TRANSACTION", "SELECT 1;"])

        with pytest.raises(MigrationError, match=re.escape("00013_late.sql")):
            parse_migration_file("00013_late.sql", text)

    def test_parse_with_interpolation(self):
        """A ``{{...}}`` interpolation inside the Up section raises naming the file and the rule."""
        text = "-- +goose Up\nCREATE TABLE {{.Name}} (id int);"

        with pytest.raises(MigrationError, match=re.escape("00014_interp.sql")) as excinfo:
            parse_migration_file("00014_interp.sql", text)

        assert "interpolation is not supported" in str(excinfo.value)


class TestLoadMigrationSet:
    """Logic of ``load_migration_set``."""

    def test_load_orders_numerically(self, tmp_path: Path):
        """The set returns in ascending numeric version order — 9 before 10, 2 first."""
        (tmp_path / "9_nine.sql").write_text("-- +goose Up\nSELECT 9;", encoding="utf-8")
        (tmp_path / "10_ten.sql").write_text("-- +goose Up\nSELECT 10;", encoding="utf-8")
        (tmp_path / "2_two.sql").write_text("-- +goose Up\nSELECT 2;", encoding="utf-8")

        migrations = load_migration_set(tmp_path)

        assert [migration.version for migration in migrations] == [2, 9, 10]
        assert [migration.filename for migration in migrations] == ["2_two.sql", "9_nine.sql", "10_ten.sql"]

    def test_load_without_sql_files(self, tmp_path: Path):
        """A folder without .sql files raises naming the folder."""
        (tmp_path / "README.md").write_text("no migrations here", encoding="utf-8")

        with pytest.raises(MigrationError, match=re.escape(str(tmp_path))):
            load_migration_set(tmp_path)

    def test_load_with_duplicate_versions(self, tmp_path: Path):
        """Two files sharing a numeric version prefix raise naming the folder and both files."""
        (tmp_path / "1_a.sql").write_text("-- +goose Up\nSELECT 1;", encoding="utf-8")
        (tmp_path / "0001_b.sql").write_text("-- +goose Up\nSELECT 1;", encoding="utf-8")

        with pytest.raises(MigrationError, match=re.escape(str(tmp_path))) as excinfo:
            load_migration_set(tmp_path)

        assert "1_a.sql" in str(excinfo.value)
        assert "0001_b.sql" in str(excinfo.value)
