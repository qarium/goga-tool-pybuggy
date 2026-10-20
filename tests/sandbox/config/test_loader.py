"""Contract and logic tests for the sandbox document validation routines."""

import inspect
import pathlib
import re

import pytest
from goga_tool_pybuggy.sandbox.config import (
    MigrationsConfig,
    SandboxConfig,
    StartupData,
    validate_sandbox_config,
)
from goga_tool_pybuggy.sandbox.migrations import MigrationError
from yaml import full_load


def validate_written(path: pathlib.Path | None = None) -> SandboxConfig:
    """Validate the written document the way the plugin does: parse, then validate.

    Args:
        path: The document location; ``None`` resolves the tools-home document of the cwd.

    Returns:
        The validated configuration model.
    """
    location = path if path is not None else pathlib.Path.cwd() / ".goga" / "tools" / "pybuggy" / "sandbox.yml"

    return validate_sandbox_config(full_load(location.read_text(encoding="utf-8")) or {}, location)


FULL_DOCUMENT = """\
instance:
  image: my-service:latest
  port: 8080
  probe:
    path: /health
  env:
    DATABASE_URL: "postgres://{{db.host}}:{{db.port}}/app"
    KAFKA_BOOTSTRAP: "{{events.host}}:{{events.port}}"
    VAULT_ADDR: "http://{{secrets.host}}:{{secrets.port}}"

services:
  db:
    kind: postgresql
    image: postgres:16-alpine
  events:
    kind: kafka
    topics:
      - name: orders.events
      - name: payments.events
        partitions: 6
  secrets:
    kind: vault
  payments:
    kind: http

data:
  vault:
    secrets:
      - path: "payment/api-key"
        data:
          api_key: "test-key"
          ttl: "1h"
  http:
    payments:
      - request:
          method: POST
          urlPath: /v1/charge
        response:
          status: 200
          jsonBody:
            status: "captured"
  postgres:
    db:
      - "CREATE TABLE IF NOT EXISTS orders (id bigint PRIMARY KEY, customer text, total numeric)"
"""


class TestValidateSandboxConfigContract:
    """Declared API of the ``validate_sandbox_config`` routine."""

    def test_validate_sandbox_config_is_importable_from_config_facade(self):
        """``validate_sandbox_config`` is re-exported by the ``goga_tool_pybuggy.sandbox.config`` facade."""
        assert callable(validate_sandbox_config)

    def test_validate_sandbox_config_declares_the_contract_signature(self):
        """The signature is ``(document: dict, location: Path | str)`` — two positional parameters."""
        parameters = list(inspect.signature(validate_sandbox_config).parameters.values())

        assert [parameter.name for parameter in parameters] == ["document", "location"]

    def test_validate_sandbox_config_returns_the_declared_type(self):
        """The return annotation is ``SandboxConfig`` — no None arm, validation always returns or raises."""
        assert inspect.signature(validate_sandbox_config).return_annotation is SandboxConfig

    def test_validate_builds_the_model_from_a_parsed_mapping(self, tmp_path):
        """A parsed document mapping validates into the same model the file reader builds."""
        document = {
            "instance": {"image": "my-service:latest", "port": 8080, "env": {}},
            "services": {"db": {"kind": "postgresql"}},
        }

        config = validate_sandbox_config(document, tmp_path / "sandbox.yml")

        assert isinstance(config, SandboxConfig)
        assert config.instance.image == "my-service:latest"
        assert config.services["db"].kind == "postgresql"

    def test_validate_failure_names_the_carried_location(self, tmp_path):
        """An invalid mapping fails naming the location the caller carried in."""
        with pytest.raises(ValueError, match=r"sandbox\.yml.*instance") as excinfo:
            validate_sandbox_config({"services": {}}, tmp_path / "sandbox.yml")

        assert "sandbox.yml" in str(excinfo.value)


class TestValidateSandboxConfigLogic:
    """Validation behavior of the parsed document mapping."""

    def test_load_resolves_document_under_tools_home(self, sandbox_yaml):
        """Scenario 1: the document resolves at ``.goga/tools/pybuggy/sandbox.yml`` from the CWD."""
        sandbox_yaml(FULL_DOCUMENT)

        config = validate_written()

        assert isinstance(config, SandboxConfig)
        assert config.instance.image == "my-service:latest"
        assert config.services["events"].topics[0].name == "orders.events"
        assert config.services["events"].topics[1].partitions == 6
        assert config.data.postgres["db"] == [
            "CREATE TABLE IF NOT EXISTS orders (id bigint PRIMARY KEY, customer text, total numeric)"
        ]
        assert not hasattr(config.data, "kafka")
        assert "kafka" not in StartupData.model_fields

    def test_load_carries_the_declared_base_path(self, sandbox_yaml):
        """A declared ``base_path`` prefix loads onto the instance entry; absent keeps ``""``."""
        sandbox_yaml(
            "instance:\n"
            "  image: my-service:latest\n"
            "  port: 8080\n"
            "  base_path: /api/v1\n"
            "  env: {}\n"
            "services:\n"
            "  db: { kind: postgresql }\n"
        )

        config = validate_written()

        assert config.instance.base_path == "/api/v1"

    def test_load_fails_naming_rename_for_service_key(self, sandbox_yaml):
        """Scenario 3: the former 'service' top-level key fails naming the rename to 'instance'."""
        path = sandbox_yaml(
            "service:\n  image: my-service:latest\n  port: 8080\n  env: {}\nservices:\n  db: { kind: postgresql }\n"
        )

        with pytest.raises(ValueError, match=r"renamed to 'instance'") as excinfo:
            validate_written()

        assert str(path) in str(excinfo.value)

    def test_load_fails_naming_rename_for_instances_key(self, sandbox_yaml):
        """Scenario 4: the former 'instances' top-level key fails naming the rename to 'services'."""
        path = sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\ninstances:\n  db: { kind: postgresql }\n"
        )

        with pytest.raises(ValueError, match=r"renamed to 'services'") as excinfo:
            validate_written()

        assert str(path) in str(excinfo.value)

    def test_load_fails_on_unknown_top_level_key(self, sandbox_yaml):
        """Scenario 5: an unknown top-level key fails listing the supported keys."""
        sandbox_yaml("instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\nextra: {}\n")

        with pytest.raises(
            ValueError, match=r"unknown top-level key 'extra' \(supported keys: instance, services, data\)"
        ):
            validate_written()

    def test_load_fails_on_kafka_entry_without_topics(self, sandbox_yaml):
        """Scenario 6: a kafka entry without topics fails at load time — nothing starts."""
        sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\nservices:\n  events: { kind: kafka }\n"
        )

        with pytest.raises(ValueError, match=r"services\.events.*topics"):
            validate_written()

    def test_load_fails_on_topics_on_non_kafka_entry(self, sandbox_yaml):
        """Scenario 7: a topics list on a non-kafka entry is rejected."""
        sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\n"
            "services:\n  db: { kind: postgresql, topics: [{name: orders.events}] }\n"
        )

        with pytest.raises(ValueError, match=r"accepted only on kafka entries"):
            validate_written()

    def test_load_fails_on_duplicate_topic_names(self, sandbox_yaml):
        """Scenario 8 (D7): duplicate topic names within one service entry are rejected."""
        sandbox_yaml(
            "instance:\n"
            "  image: my-service:latest\n"
            "  port: 8080\n"
            "  env: {}\n"
            "services:\n"
            "  events:\n"
            "    kind: kafka\n"
            "    topics:\n"
            "      - { name: orders.events }\n"
            "      - { name: orders.events, partitions: 3 }\n"
        )

        with pytest.raises(ValueError, match=r"duplicate topic 'orders\.events'"):
            validate_written()

    def test_load_fails_on_probe_path_on_service(self, sandbox_yaml):
        """Scenario 9 (D1): a probe path on a service entry fails naming the entry scope."""
        sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\n"
            "services:\n  secrets: { kind: vault, probe: { path: /health } }\n"
        )

        with pytest.raises(ValueError, match=r"services\.secrets.*probe path"):
            validate_written()

    @pytest.mark.parametrize(
        ("probe_entry", "field"),
        [
            ("timeout: 0", "timeout"),
            ("interval: -1", "interval"),
            ("interval: 60", "interval"),
        ],
    )
    def test_load_fails_on_probe_bounds(self, sandbox_yaml, probe_entry, field):
        """Scenario 10: out-of-bounds probe declarations fail naming the probe field."""
        sandbox_yaml(
            "instance:\n"
            "  image: my-service:latest\n"
            "  port: 8080\n"
            "  env: {}\n"
            "services:\n"
            "  db:\n"
            "    kind: postgresql\n"
            "    probe:\n"
            f"      {probe_entry}\n"
        )

        with pytest.raises(ValueError, match=rf"probe.*{field}"):
            validate_written()

    def test_load_accepts_interval_equal_to_timeout(self, sandbox_yaml):
        """Scenario 10 boundary: ``interval == timeout`` is the legal edge of the comparator."""
        sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\n"
            "services:\n  db: { kind: postgresql, probe: { timeout: 30.0, interval: 30.0 } }\n"
        )

        config = validate_written()

        assert config.services["db"].probe.timeout == 30.0
        assert config.services["db"].probe.interval == 30.0

    def test_load_fails_on_removed_kafka_data_section(self, sandbox_yaml):
        """Scenario 11: a kafka data section fails as removed — the topology lives on the entry."""
        sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\n"
            "services:\n  events: { kind: kafka, topics: [{name: orders.events}] }\n"
            "data:\n  kafka:\n    events: asyncapi.yaml\n"
        )

        with pytest.raises(ValueError, match=r"data\.kafka was removed"):
            validate_written()

    def test_load_fails_on_placeholder_naming_unknown_service(self, sandbox_yaml):
        """Scenario 12: an env placeholder naming an unconfigured service fails listing them."""
        sandbox_yaml(
            "instance:\n"
            "  image: my-service:latest\n"
            "  port: 8080\n"
            "  env:\n"
            '    DATABASE_URL: "postgres://{{nope.host}}:5432/app"\n'
            "services:\n"
            "  db: { kind: postgresql }\n"
        )

        with pytest.raises(ValueError, match=r"'nope' is not configured \(configured services: db\)"):
            validate_written()

    def test_load_rejects_hyphenated_service_name(self, sandbox_yaml):
        """Scenario 13: a hyphenated service name fails the template-identifier grammar."""
        sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\nservices:\n  my-db: { kind: postgresql }\n"
        )

        with pytest.raises(ValueError, match=r"services\.my-db.*template identifier"):
            validate_written()

    def test_load_grpc_kind_fails_not_supported_yet(self, sandbox_yaml):
        """Scenario 14: the grpc kind fails with the explicit 'not supported yet' error."""
        sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\nservices:\n  broker: { kind: grpc }\n"
        )

        with pytest.raises(ValueError, match=r"grpc.*not supported yet"):
            validate_written()

    def test_load_probe_defaults_applied(self, sandbox_yaml):
        """Scenario 15: empty and partial probe blocks keep the established defaults."""
        sandbox_yaml(
            "instance:\n"
            "  image: my-service:latest\n"
            "  port: 8080\n"
            "  probe: {}\n"
            "  env: {}\n"
            "services:\n"
            "  db: { kind: postgresql, probe: { timeout: 45.0 } }\n"
        )

        config = validate_written()

        assert config.instance.probe.timeout == 30.0
        assert config.instance.probe.interval == 0.5
        assert config.instance.probe.path is None
        assert config.services["db"].probe.timeout == 45.0
        assert config.services["db"].probe.interval == 0.5

    def test_load_returns_validated_model_for_full_document(self, sandbox_yaml):
        """The full authoring example loads into a validated model with inline topics."""
        sandbox_yaml(FULL_DOCUMENT)

        config = validate_written()

        assert isinstance(config, SandboxConfig)
        assert config.instance.image == "my-service:latest"
        assert config.instance.port == 8080
        assert config.instance.probe.path == "/health"
        assert config.instance.env["DATABASE_URL"] == "postgres://{{db.host}}:{{db.port}}/app"
        assert config.instance.env["KAFKA_BOOTSTRAP"] == "{{events.host}}:{{events.port}}"
        assert config.instance.env["VAULT_ADDR"] == "http://{{secrets.host}}:{{secrets.port}}"
        assert set(config.services) == {"db", "events", "secrets", "payments"}
        assert config.services["db"].kind == "postgresql"
        assert config.services["db"].image == "postgres:16-alpine"
        assert config.services["events"].image is None
        assert [topic.name for topic in config.services["events"].topics] == ["orders.events", "payments.events"]
        assert config.services["events"].probe is None
        assert config.data.vault == {
            "secrets": [{"path": "payment/api-key", "data": {"api_key": "test-key", "ttl": "1h"}}]
        }
        assert config.data.http == {
            "payments": [
                {
                    "request": {"method": "POST", "urlPath": "/v1/charge"},
                    "response": {"status": 200, "jsonBody": {"status": "captured"}},
                }
            ]
        }
        assert config.data.postgres == {
            "db": ["CREATE TABLE IF NOT EXISTS orders (id bigint PRIMARY KEY, customer text, total numeric)"]
        }

    def test_load_fails_missing_required_instance_field(self, sandbox_yaml):
        """A missing required instance field fails naming the field."""
        sandbox_yaml("instance:\n  image: my-service:latest\n  env: {}\n")

        with pytest.raises(ValueError, match=r"instance\.port"):
            validate_written()

    def test_load_fails_missing_instance_section(self, sandbox_yaml):
        """A document without the instance entry fails naming the entry."""
        sandbox_yaml("services:\n  db: { kind: postgresql }\n")

        with pytest.raises(ValueError, match=r"sandbox\.yml.*instance"):
            validate_written()

    def test_load_fails_unknown_service_kind(self, sandbox_yaml):
        """A kind outside the five supported ones fails listing them."""
        sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\nservices:\n  cache: { kind: mysql }\n"
        )

        with pytest.raises(ValueError, match=r"mysql.*postgresql.*kafka.*vault.*http.*redis"):
            validate_written()

    def test_load_fails_data_targeting_unknown_service(self, sandbox_yaml):
        """A data declaration targeting an unconfigured service fails naming the target."""
        sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\n"
            "services:\n  db: { kind: postgresql }\n"
            'data:\n  postgres:\n    nodb:\n      - "CREATE TABLE orders (id int)"\n'
        )

        with pytest.raises(ValueError, match=r"nodb"):
            validate_written()

    def test_load_fails_data_targeting_service_of_wrong_kind(self, sandbox_yaml):
        """A data section targeting a service of another kind fails naming both kinds."""
        sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\n"
            "services:\n  events: { kind: kafka, topics: [{name: orders.events}] }\n"
            'data:\n  postgres:\n    events:\n      - "CREATE TABLE orders (id int)"\n'
        )

        with pytest.raises(ValueError, match=r"events.*kafka.*postgresql"):
            validate_written()

    def test_validate_fails_empty_document(self, sandbox_yaml):
        """A zero-byte document is an invalid document — the error names the location."""
        path = sandbox_yaml("")

        with pytest.raises(ValueError, match=r"sandbox\.yml.*instance") as excinfo:
            validate_written(path)

        assert str(path) in str(excinfo.value)

    @pytest.mark.parametrize(
        ("document", "match"),
        [
            ("instance:\n  image: i\n  port: 1\n  env: {}\nservices: []", r"services.*mapping"),
            (
                "instance:\n  image: i\n  port: 1\n  env: {}\nservices:\n  ' ': { kind: postgresql }",
                r"services.*non-empty string",
            ),
            ("instance:\n  image: i\n  port: 1\n  env: {}\nservices:\n  db: oops", r"services\.db.*mapping"),
            (
                "instance:\n  image: i\n  port: 1\n  env: {}\nservices:\n  db: { image: x }",
                r"services\.db\.kind.*missing",
            ),
            (
                "instance:\n  image: i\n  port: 1\n  env: {}\nservices:\n  db: { kind: }\n",
                r"services\.db\.kind.*missing",
            ),
            ("instance:\n  image: i\n  port: 1\n  env: {}\nservices: {}\ndata: []", r"data.*mapping"),
            (
                "instance:\n  image: i\n  port: 1\n  env: {}\nservices:\n  db: { kind: postgresql }\n"
                "data:\n  postgres: oops",
                r"data\.postgres.*mapping",
            ),
            (
                "instance:\n  image: i\n  port: 1\n  env: {}\nservices: {}\ndata:\n  cache: {}",
                r"data\.cache.*unknown data section.*vault, http, postgres, redis",
            ),
            (
                "instance:\n  image: i\n  port: [1]\n  env: {}\nservices: {}",
                r"instance.*port.*Input should be a valid integer",
            ),
            (
                "instance:\n  image: i\n  port: 1\n  env: {}\nservices:\n  events:\n    kind: kafka\n    topics: oops",
                r"services\.events.*topics",
            ),
            (
                "instance:\n  image: i\n  port: 1\n  env: {}\nservices:\n  events: { kind: kafka, topics: [7] }",
                r"services\.events\.topics.*mapping",
            ),
        ],
    )
    def test_load_fails_malformed_entries_naming_the_location(self, sandbox_yaml, document, match):
        """Every malformed entry branch fails with the location and the offending entry named."""
        sandbox_yaml(document)

        with pytest.raises(ValueError, match=match):
            validate_written()

    @pytest.mark.parametrize(
        "name",
        ["my-db", "1db", "db.two", "events!"],
    )
    def test_load_fails_service_name_that_is_not_a_template_identifier(self, sandbox_yaml, name):
        """Service names double as Jinja2 placeholder identifiers — anything else fails."""
        sandbox_yaml(f"instance:\n  image: i\n  port: 1\n  env: {{}}\nservices:\n  {name}: {{ kind: postgresql }}\n")

        with pytest.raises(ValueError, match=rf"services\.{re.escape(name)}.*template identifier"):
            validate_written()

    def test_load_fails_bare_service_placeholder(self, sandbox_yaml):
        """A bare service name without the host/port attribute fails naming the env key."""
        sandbox_yaml(
            "instance:\n"
            "  image: my-service:latest\n"
            "  port: 8080\n"
            "  env:\n"
            '    KAFKA_BOOTSTRAP: "{{events}}"\n'
            "services:\n"
            "  events: { kind: kafka, topics: [{name: orders.events}] }\n"
        )

        with pytest.raises(ValueError, match=r"KAFKA_BOOTSTRAP.*missing its '\.host' or '\.port'"):
            validate_written()

    def test_load_fails_unknown_placeholder_attribute(self, sandbox_yaml):
        """A placeholder attribute outside host/port fails naming the env key and the attribute."""
        sandbox_yaml(
            "instance:\n"
            "  image: my-service:latest\n"
            "  port: 8080\n"
            "  env:\n"
            '    DATABASE_URL: "{{db.hst}}"\n'
            "services:\n"
            "  db: { kind: postgresql }\n"
        )

        with pytest.raises(ValueError, match=r"DATABASE_URL.*hst"):
            validate_written()

    def test_load_fails_unterminated_placeholder_in_env_value(self, sandbox_yaml):
        """An env value with an unterminated ``{{`` fails at load time, not at render time."""
        sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env:\n"
            '    DATABASE_URL: "postgres://{{db.host:5432/app"\n'
            "services:\n"
            "  db: { kind: postgresql }\n"
        )

        with pytest.raises(ValueError, match=r"DATABASE_URL.*unterminated.*'\{\{'"):
            validate_written()

    @pytest.mark.parametrize(
        "value",
        [
            "{% set db = {'host': 'h'} %}x",
            "{# a comment #}x",
        ],
    )
    def test_load_fails_on_jinja_statement_or_comment_syntax(self, sandbox_yaml, value):
        """Jinja2 statement/comment blocks are not placeholders — they never reach render time."""
        sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env:\n"
            f'    DATABASE_URL: "{value}"\n'
            "services:\n"
            "  db: { kind: postgresql }\n"
        )

        with pytest.raises(
            ValueError, match=r"DATABASE_URL.*statement or comment syntax is not part of the placeholder grammar"
        ):
            validate_written()

    @pytest.mark.parametrize(
        ("document", "match"),
        [
            (
                "instance:\n  image: i\n  port: 1\n  env: {}\n  replicas: 2\nservices: {}",
                r"instance.*replicas.*Extra inputs are not permitted",
            ),
            (
                "instance:\n  image: i\n  port: 1\n  env: {}\n  prob: {path: /health}\nservices: {}",
                r"instance.*prob.*Extra inputs are not permitted",
            ),
            (
                "instance:\n  image: i\n  port: 1\n  env: {}\nservices:\n  db: { kind: postgresql, imag: postgres:17 }",
                r"services\.db.*imag.*Extra inputs are not permitted",
            ),
            (
                "instance:\n  image: i\n  port: 1\n  env: {}\nservices:\n"
                "  events: { kind: kafka, topics: [{name: t, partition: 6}] }",
                r"services\.events\.topics.*partition.*Extra inputs are not permitted",
            ),
            (
                "instance:\n  image: i\n  port: 1\n  env: {}\n  probe: {path: health, timeout: 3}\nservices: {}",
                r"instance.*probe.*path must start with '/'",
            ),
            (
                "instance:\n  image: i\n  port: 1\n  env: {}\n  base_path: api/v1\nservices: {}",
                r"instance.*base_path must start with '/'",
            ),
        ],
    )
    def test_load_fails_on_unknown_or_malformed_entry_keys(self, sandbox_yaml, document, match):
        """A mistyped entry key (``imag`` for ``image``) fails at load instead of silently
        dropping the declaration; a health path or an API path prefix without the leading
        slash fails the same way."""
        sandbox_yaml(document)

        with pytest.raises(ValueError, match=match):
            validate_written()

    @pytest.mark.parametrize("name", ["true", "false", "none", "True", "None"])
    def test_load_fails_on_jinja_literal_service_names(self, sandbox_yaml, name):
        """The Jinja2 literal names parse as constants, not variables — placeholders over them
        could never resolve, so the names are rejected with the identifier-grammar error.
        The name is quoted so YAML hands the loader a string, not a native bool or null."""
        sandbox_yaml(f"instance:\n  image: i\n  port: 1\n  env: {{}}\nservices:\n  '{name}': {{ kind: postgresql }}\n")

        with pytest.raises(ValueError, match=rf"services\.{name}.*template identifier"):
            validate_written()

    @pytest.mark.parametrize(
        ("declaration", "match"),
        [
            ("- { data: {k: v} }", r"data\.vault\.secrets.*non-empty string 'path'"),
            ("- { path: 7, data: {k: v} }", r"data\.vault\.secrets.*non-empty string 'path'"),
            ("- { path: p }", r"data\.vault\.secrets.*mapping 'data'"),
            ("- { path: p, data: oops }", r"data\.vault\.secrets.*mapping 'data'"),
        ],
    )
    def test_load_fails_vault_declaration_of_wrong_shape(self, sandbox_yaml, declaration, match):
        """A malformed vault secret declaration fails at load time naming the section."""
        sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "services:\n"
            "  secrets: { kind: vault }\n"
            "data:\n"
            "  vault:\n"
            f"    secrets:\n      {declaration}\n"
        )

        with pytest.raises(ValueError, match=match):
            validate_written()


MIGRATION_FILE = "-- +goose Up\nCREATE TABLE orders (id bigint PRIMARY KEY);\n"


class TestValidateSandboxConfigMigrationsContract:
    """Contract of the migrations validation step."""

    def test_migrations_declaration_is_observable_through_the_validator(self, sandbox_yaml, tmp_path):
        """A migrations-declaring document loads into the typed ``ServiceConfig.migrations``."""
        folder = tmp_path / "db" / "migrations"
        folder.mkdir(parents=True)
        (folder / "00001_init.sql").write_text(MIGRATION_FILE, encoding="utf-8")
        sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "services:\n"
            "  db:\n"
            "    kind: postgresql\n"
            "    migrations:\n"
            "      location: db/migrations\n"
        )

        config = validate_written()

        assert isinstance(config.services["db"].migrations, MigrationsConfig)


class TestValidateSandboxConfigMigrationsLogic:
    """Validation behavior of the migrations declaration step."""

    def test_loader_accepts_migrations_on_postgresql(self, sandbox_yaml, tmp_path):
        """A local source with a valid on-disk folder loads into the typed declaration."""
        folder = tmp_path / "db" / "migrations"
        folder.mkdir(parents=True)
        (folder / "00001_init.sql").write_text(MIGRATION_FILE, encoding="utf-8")
        sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "services:\n"
            "  db:\n"
            "    kind: postgresql\n"
            "    migrations:\n"
            "      location: db/migrations\n"
        )

        config = validate_written()

        assert config.services["db"].migrations.location == "db/migrations"
        assert config.services["db"].migrations.git is None

    def test_loader_accepts_remote_source_by_shape(self, sandbox_yaml):
        """A remote source loads by URL shape only — no folder on disk, no network."""
        sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "services:\n"
            "  db:\n"
            "    kind: postgresql\n"
            "    migrations:\n"
            "      location: db/migrations\n"
            "      git:\n"
            "        url: https://gitlab.example/acme/s.git\n"
        )

        config = validate_written()

        assert config.services["db"].migrations.git.url == "https://gitlab.example/acme/s.git"
        assert config.services["db"].migrations.git.ref is None

    def test_loader_rejects_migrations_on_non_postgresql(self, sandbox_yaml, tmp_path):
        """A declaration on a kafka entry fails naming the entry — even with a valid folder."""
        folder = tmp_path / "db" / "migrations"
        folder.mkdir(parents=True)
        (folder / "00001_init.sql").write_text(MIGRATION_FILE, encoding="utf-8")
        path = sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "services:\n"
            "  events:\n"
            "    kind: kafka\n"
            "    topics: [{name: orders.events}]\n"
            "    migrations:\n"
            "      location: db/migrations\n"
        )

        with pytest.raises(ValueError, match=r"services\.events.*accepted only on postgresql entries") as excinfo:
            validate_written()

        assert str(path) in str(excinfo.value)

    @pytest.mark.parametrize(
        "migrations_entry",
        [
            "",
            "12",
            "x",
        ],
    )
    def test_loader_rejects_non_mapping_migrations_value(self, sandbox_yaml, migrations_entry):
        """A null, list or scalar migrations value fails as exactly a ValueError — no TypeError."""
        path = sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "services:\n"
            "  db:\n"
            "    kind: postgresql\n"
            f"    migrations: {migrations_entry}\n"
        )

        with pytest.raises(ValueError, match=r"services\.db\.migrations: must be a mapping") as excinfo:
            validate_written()

        assert excinfo.type is ValueError
        message = str(excinfo.value)
        assert str(path) in message
        assert "services.db" in message
        assert "migrations" in message

    def test_loader_rejects_empty_migrations_location(self, sandbox_yaml, tmp_path):
        """An empty location fails the guard — it would resolve to the cwd or the clone root."""
        (tmp_path / "00001_root.sql").write_text(MIGRATION_FILE, encoding="utf-8")
        sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "services:\n"
            "  db:\n"
            "    kind: postgresql\n"
            "    migrations:\n"
            '      location: ""\n'
        )

        with pytest.raises(ValueError, match=r"migrations\.location: must be a non-empty path") as excinfo:
            validate_written()

        assert excinfo.type is ValueError

    def test_loader_rejects_missing_local_folder(self, sandbox_yaml):
        """A declared local folder absent from disk fails with the MigrationError as the cause."""
        path = sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "services:\n"
            "  db:\n"
            "    kind: postgresql\n"
            "    migrations:\n"
            "      location: db/migrations\n"
        )

        with pytest.raises(ValueError, match=r"migrations: .*must be an existing folder") as excinfo:
            validate_written()

        message = str(excinfo.value)
        assert str(path) in message
        assert "db/migrations" in message
        assert isinstance(excinfo.value.__cause__, MigrationError)

    def test_loader_rejects_bad_git_url_scheme(self, sandbox_yaml):
        """A remote URL outside the scheme allowlist fails wrapped with the scope."""
        sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "services:\n"
            "  db:\n"
            "    kind: postgresql\n"
            "    migrations:\n"
            "      location: db/migrations\n"
            "      git:\n"
            "        url: ftp://h/r.git\n"
        )

        with pytest.raises(ValueError, match=r"services\.db\.migrations: .*disallowed git URL scheme 'ftp'") as excinfo:
            validate_written()

        assert isinstance(excinfo.value.__cause__, MigrationError)

    def test_loader_rejects_duplicate_versions_at_load(self, sandbox_yaml, tmp_path):
        """Duplicate numeric version prefixes in the declared folder fail naming both files."""
        folder = tmp_path / "db" / "migrations"
        folder.mkdir(parents=True)
        (folder / "1_a.sql").write_text(MIGRATION_FILE, encoding="utf-8")
        (folder / "0001_b.sql").write_text(MIGRATION_FILE, encoding="utf-8")
        path = sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "services:\n"
            "  db:\n"
            "    kind: postgresql\n"
            "    migrations:\n"
            "      location: db/migrations\n"
        )

        with pytest.raises(ValueError, match=r"services\.db\.migrations: .*duplicate migration version 1") as excinfo:
            validate_written()

        message = str(excinfo.value)
        assert str(path) in message
        assert "1_a.sql" in message
        assert "0001_b.sql" in message
        assert isinstance(excinfo.value.__cause__, MigrationError)


class TestValidateSandboxConfigRedisContract:
    """Contract of the redis kind and ``data.redis`` validation steps."""

    def test_load_accepts_a_redis_service_with_password_and_db(self, sandbox_yaml):
        """A redis entry carrying password and db loads into the typed ``ServiceConfig``."""
        sandbox_yaml(
            "instance:\n"
            "  image: my-service:latest\n"
            "  port: 8080\n"
            "  env: {}\n"
            "services:\n"
            "  cache: { kind: redis, password: sandbox-redis, db: 2 }\n"
        )

        config = validate_written()

        assert config.services["cache"].kind == "redis"
        assert config.services["cache"].password == "sandbox-redis"
        assert config.services["cache"].db == 2


class TestValidateSandboxConfigRedisLogic:
    """Validation behavior of the redis kind and the ``data.redis`` section."""

    def test_load_accepts_the_redis_data_section_for_all_four_actions(self, sandbox_yaml):
        """The four action declarations load and reach the model verbatim, in order."""
        sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "services:\n"
            "  cache: { kind: redis }\n"
            "data:\n"
            "  redis:\n"
            "    cache:\n"
            "      - { action: set, key: feature-flag/a, value: enabled }\n"
            '      - { action: hset, key: "user:1", values: { name: Ann } }\n'
            '      - { action: rpush, key: "queue:orders", values: [{ id: 1 }, { id: 2 }] }\n'
            '      - { action: sadd, key: "members:vip", members: [ann, bob] }\n'
        )

        config = validate_written()

        assert config.data.redis["cache"] == [
            {"action": "set", "key": "feature-flag/a", "value": "enabled"},
            {"action": "hset", "key": "user:1", "values": {"name": "Ann"}},
            {"action": "rpush", "key": "queue:orders", "values": [{"id": 1}, {"id": 2}]},
            {"action": "sadd", "key": "members:vip", "members": ["ann", "bob"]},
        ]

    def test_load_accepts_redis_placeholders_in_instance_env(self, sandbox_yaml):
        """The generic placeholder path covers redis host and port references."""
        sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env:\n"
            '    REDIS_URL: "redis://{{cache.host}}:{{cache.port}}/0"\n'
            "services:\n"
            "  cache: { kind: redis }\n"
        )

        config = validate_written()

        assert config.instance.env["REDIS_URL"] == "redis://{{cache.host}}:{{cache.port}}/0"

    def test_load_fails_password_on_a_non_redis_entry(self, sandbox_yaml):
        """A password on a non-redis entry fails naming the entry."""
        sandbox_yaml(
            "instance:\n  image: i\n  port: 1\n  env: {}\nservices:\n  db: { kind: postgresql, password: x }\n"
        )

        with pytest.raises(ValueError, match=r"services\.db.*password and db are accepted only on redis entries"):
            validate_written()

    def test_load_fails_db_on_a_non_redis_entry(self, sandbox_yaml):
        """A db on a non-redis entry fails naming the entry."""
        sandbox_yaml("instance:\n  image: i\n  port: 1\n  env: {}\nservices:\n  payments: { kind: http, db: 3 }\n")

        with pytest.raises(ValueError, match=r"services\.payments.*password and db are accepted only on redis entries"):
            validate_written()

    @pytest.mark.parametrize("db", [16, -1])
    def test_load_fails_db_outside_the_range(self, sandbox_yaml, db):
        """A db index outside 0-15 fails naming the entry and the range."""
        sandbox_yaml(
            f"instance:\n  image: i\n  port: 1\n  env: {{}}\nservices:\n  cache: {{ kind: redis, db: {db} }}\n"
        )

        with pytest.raises(ValueError, match=r"services\.cache\.db: must be an integer within 0-15"):
            validate_written()

    @pytest.mark.parametrize("db_entry", ["2.5", '"2"', "true"])
    def test_load_fails_db_of_wrong_type(self, sandbox_yaml, db_entry):
        """A non-integer db — float, string, or bool — fails the same db error."""
        sandbox_yaml(
            f"instance:\n  image: i\n  port: 1\n  env: {{}}\nservices:\n  cache: {{ kind: redis, db: {db_entry} }}\n"
        )

        with pytest.raises(ValueError, match=r"services\.cache\.db: must be an integer within 0-15"):
            validate_written()

    @pytest.mark.parametrize("password_entry", ['""', "123"])
    def test_load_fails_empty_or_mistyped_password(self, sandbox_yaml, password_entry):
        """An empty or non-string password fails naming the entry and the rule."""
        sandbox_yaml(
            f"instance:\n  image: i\n  port: 1\n  env: {{}}\n"
            f"services:\n  cache: {{ kind: redis, password: {password_entry} }}\n"
        )

        with pytest.raises(ValueError, match=r"services\.cache\.password: must be a non-empty string"):
            validate_written()

    @pytest.mark.parametrize(
        "password",
        ['"my secret"', "'pa\"ss'", '"pa\\\\ss"'],
    )
    def test_load_fails_password_with_command_breaking_characters(self, sandbox_yaml, password):
        """A password carrying whitespace, quotes, or backslashes fails the load naming the rule."""
        sandbox_yaml(
            f"instance:\n  image: i\n  port: 1\n  env: {{}}\n"
            f"services:\n  cache: {{ kind: redis, password: {password} }}\n"
        )

        with pytest.raises(
            ValueError,
            match=r"services\.cache\.password: must carry no whitespace, quotes, or backslashes",
        ):
            validate_written()

    def test_load_fails_topics_on_redis(self, sandbox_yaml):
        """A topics list on a redis entry is rejected by the kafka-only placement check."""
        sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "services:\n"
            "  cache: { kind: redis, topics: [{name: orders.events}] }\n"
        )

        with pytest.raises(ValueError, match=r"services\.cache: topics are accepted only on kafka entries"):
            validate_written()

    def test_load_fails_migrations_on_redis(self, sandbox_yaml):
        """A migrations declaration on a redis entry is rejected by the postgresql-only check."""
        sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "services:\n"
            "  cache: { kind: redis, migrations: { location: x } }\n"
        )

        with pytest.raises(ValueError, match=r"services\.cache: migrations are accepted only on postgresql entries"):
            validate_written()

    def test_load_fails_redis_declaration_without_action(self, sandbox_yaml):
        """A data.redis declaration without the action key fails naming the section."""
        sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "services:\n"
            "  cache: { kind: redis }\n"
            "data:\n"
            "  redis:\n"
            "    cache:\n"
            "      - { key: k, value: v }\n"
        )

        with pytest.raises(
            ValueError,
            match=r"data\.redis\.cache: every declaration requires an 'action' key \(set, hset, rpush, or sadd\)",
        ):
            validate_written()

    def test_load_fails_redis_declaration_with_unknown_action(self, sandbox_yaml):
        """An action outside the four commands fails with the action-key error."""
        sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "services:\n"
            "  cache: { kind: redis }\n"
            "data:\n"
            "  redis:\n"
            "    cache:\n"
            "      - { action: zadd, key: k, value: v }\n"
        )

        with pytest.raises(
            ValueError,
            match=r"data\.redis\.cache: every declaration requires an 'action' key \(set, hset, rpush, or sadd\)",
        ):
            validate_written()

    def test_load_fails_redis_declaration_with_non_string_action(self, sandbox_yaml):
        """A non-string action value fails the action-key error instead of a type crash."""
        sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "services:\n"
            "  cache: { kind: redis }\n"
            "data:\n"
            "  redis:\n"
            "    cache:\n"
            "      - { action: [set], key: k, value: v }\n"
        )

        with pytest.raises(
            ValueError,
            match=r"data\.redis\.cache: every declaration requires an 'action' key \(set, hset, rpush, or sadd\)",
        ):
            validate_written()

    @pytest.mark.parametrize(
        "declaration",
        [
            "{ action: set, key: k }",
            "{ action: hset, key: k }",
            "{ action: rpush, key: k, values: [a], members: [b] }",
            "{ action: set, key: k, value: v, values: [v] }",
        ],
    )
    def test_load_fails_redis_declaration_with_missing_or_extra_fields(self, sandbox_yaml, declaration):
        """A declaration whose key set differs from the action's fields fails naming them."""
        sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "services:\n"
            "  cache: { kind: redis }\n"
            "data:\n"
            "  redis:\n"
            "    cache:\n"
            f"      - {declaration}\n"
        )

        with pytest.raises(
            ValueError, match=r"data\.redis\.cache: a '(set|hset|rpush|sadd)' declaration carries exactly"
        ):
            validate_written()

    @pytest.mark.parametrize(
        ("declaration", "field"),
        [
            ("{ action: hset, key: k, values: [1] }", "values"),
            ("{ action: rpush, key: k, values: { a: 1 } }", "values"),
            ("{ action: sadd, key: k, members: x }", "members"),
            ("{ action: set, key: 5, value: v }", "key"),
            ("{ action: set, key: '  ', value: v }", "key"),
        ],
    )
    def test_load_fails_redis_declaration_with_wrong_field_types(self, sandbox_yaml, declaration, field):
        """A mistyped declaration field fails naming the section and the field."""
        sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "services:\n"
            "  cache: { kind: redis }\n"
            "data:\n"
            "  redis:\n"
            "    cache:\n"
            f"      - {declaration}\n"
        )

        with pytest.raises(ValueError, match=rf"data\.redis\.cache.*{field}"):
            validate_written()

    @pytest.mark.parametrize(
        ("section", "detail"),
        [
            ("cache: not-a-list", r"redis\.cache: Input should be a valid list"),
            ("cache:\n      - set", r"redis\.cache\.0: Input should be a valid dictionary"),
        ],
    )
    def test_load_fails_a_malformed_redis_section_at_the_model_build(self, sandbox_yaml, section, detail):
        """Non-list section values and non-mapping declarations fail the model build naming the scope."""
        sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "services:\n"
            "  cache: { kind: redis }\n"
            "data:\n"
            "  redis:\n"
            f"    {section}\n"
        )

        with pytest.raises(ValueError, match=rf"data: {detail}"):
            validate_written()

    def test_load_fails_redis_section_targeting_a_non_redis_service(self, sandbox_yaml):
        """A data.redis target of another kind fails naming both kinds."""
        sandbox_yaml(
            "instance:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "services:\n"
            "  db: { kind: postgresql }\n"
            "data:\n"
            "  redis:\n"
            "    db:\n"
            "      - { action: set, key: k, value: v }\n"
        )

        with pytest.raises(
            ValueError,
            match=r"data\.redis\.db: targets service 'db' of kind 'postgresql', the section requires kind 'redis'",
        ):
            validate_written()

    @pytest.mark.parametrize("db", [0, 15])
    def test_load_accepts_db_boundaries_zero_and_fifteen(self, sandbox_yaml, db):
        """The inclusive range boundaries load and the value reaches the model."""
        sandbox_yaml(
            f"instance:\n  image: i\n  port: 1\n  env: {{}}\nservices:\n  cache: {{ kind: redis, db: {db} }}\n"
        )

        config = validate_written()

        assert config.services["cache"].db == db

    def test_load_ignores_absent_password_and_db(self, sandbox_yaml):
        """A bare redis entry keeps the model defaults — the primary no-auth mode."""
        sandbox_yaml("instance:\n  image: i\n  port: 1\n  env: {}\nservices:\n  cache: { kind: redis }\n")

        config = validate_written()

        assert config.services["cache"].password is None
        assert config.services["cache"].db == 0
