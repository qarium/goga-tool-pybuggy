"""Contract and logic tests for the ``load_sandbox_config`` routine."""

import inspect
import re

import pytest
from goga_tool_pybuggy.sandbox.config import SandboxConfig, StartupData, load_sandbox_config

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


class TestLoadSandboxConfigContract:
    """Declared API of the ``load_sandbox_config`` routine."""

    def test_load_sandbox_config_is_importable_from_config_facade(self):
        """``load_sandbox_config`` is re-exported by the ``goga_tool_pybuggy.sandbox.config`` facade."""
        assert callable(load_sandbox_config)

    def test_load_sandbox_config_declares_the_contract_signature(self):
        """The signature is ``(path: str | None)`` — one optional positional parameter."""
        parameters = list(inspect.signature(load_sandbox_config).parameters.values())

        assert len(parameters) == 1
        assert parameters[0].name == "path"
        assert parameters[0].default is None

    def test_load_sandbox_config_returns_the_declared_types(self):
        """The return annotation is ``SandboxConfig | None``."""
        annotation = inspect.signature(load_sandbox_config).return_annotation

        assert annotation == SandboxConfig | None


class TestLoadSandboxConfigLogic:
    """Reading and validation behavior of the loader."""

    def test_load_resolves_document_under_tools_home(self, sandbox_yaml):
        """Scenario 1: the document resolves at ``.goga/tools/pybuggy/sandbox.yml`` from the CWD."""
        sandbox_yaml(FULL_DOCUMENT)

        config = load_sandbox_config(None)

        assert isinstance(config, SandboxConfig)
        assert config.instance.image == "my-service:latest"
        assert config.services["events"].topics[0].name == "orders.events"
        assert config.services["events"].topics[1].partitions == 6
        assert config.data.postgres["db"] == [
            "CREATE TABLE IF NOT EXISTS orders (id bigint PRIMARY KEY, customer text, total numeric)"
        ]
        assert not hasattr(config.data, "kafka")
        assert "kafka" not in StartupData.model_fields

    def test_load_returns_none_without_document_and_ignores_stale_root_document(self, tmp_path, monkeypatch):
        """Scenario 2: an absent tools-home document stays inert; a stale root document is never read."""
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".sandbox.yml").write_text(
            "service:\n  image: my-service:latest\n  port: 8080\n  env: {}\n", encoding="utf-8"
        )

        assert load_sandbox_config(None) is None

    def test_load_fails_naming_rename_for_service_key(self, sandbox_yaml):
        """Scenario 3: the former 'service' top-level key fails naming the rename to 'instance'."""
        path = sandbox_yaml(
            "service:\n  image: my-service:latest\n  port: 8080\n  env: {}\nservices:\n  db: { kind: postgresql }\n"
        )

        with pytest.raises(ValueError, match=r"renamed to 'instance'") as excinfo:
            load_sandbox_config(None)

        assert str(path) in str(excinfo.value)

    def test_load_fails_naming_rename_for_instances_key(self, sandbox_yaml):
        """Scenario 4: the former 'instances' top-level key fails naming the rename to 'services'."""
        path = sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\ninstances:\n  db: { kind: postgresql }\n"
        )

        with pytest.raises(ValueError, match=r"renamed to 'services'") as excinfo:
            load_sandbox_config(None)

        assert str(path) in str(excinfo.value)

    def test_load_fails_on_unknown_top_level_key(self, sandbox_yaml):
        """Scenario 5: an unknown top-level key fails listing the supported keys."""
        sandbox_yaml("instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\nextra: {}\n")

        with pytest.raises(
            ValueError, match=r"unknown top-level key 'extra' \(supported keys: instance, services, data\)"
        ):
            load_sandbox_config(None)

    def test_load_fails_on_kafka_entry_without_topics(self, sandbox_yaml):
        """Scenario 6: a kafka entry without topics fails at load time — nothing starts."""
        sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\nservices:\n  events: { kind: kafka }\n"
        )

        with pytest.raises(ValueError, match=r"services\.events.*topics"):
            load_sandbox_config(None)

    def test_load_fails_on_topics_on_non_kafka_entry(self, sandbox_yaml):
        """Scenario 7: a topics list on a non-kafka entry is rejected."""
        sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\n"
            "services:\n  db: { kind: postgresql, topics: [{name: orders.events}] }\n"
        )

        with pytest.raises(ValueError, match=r"accepted only on kafka entries"):
            load_sandbox_config(None)

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
            load_sandbox_config(None)

    def test_load_fails_on_probe_path_on_service(self, sandbox_yaml):
        """Scenario 9 (D1): a probe path on a service entry fails naming the entry scope."""
        sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\n"
            "services:\n  secrets: { kind: vault, probe: { path: /health } }\n"
        )

        with pytest.raises(ValueError, match=r"services\.secrets.*probe path"):
            load_sandbox_config(None)

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
            load_sandbox_config(None)

    def test_load_accepts_interval_equal_to_timeout(self, sandbox_yaml):
        """Scenario 10 boundary: ``interval == timeout`` is the legal edge of the comparator."""
        sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\n"
            "services:\n  db: { kind: postgresql, probe: { timeout: 30.0, interval: 30.0 } }\n"
        )

        config = load_sandbox_config(None)

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
            load_sandbox_config(None)

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
            load_sandbox_config(None)

    def test_load_rejects_hyphenated_service_name(self, sandbox_yaml):
        """Scenario 13: a hyphenated service name fails the template-identifier grammar."""
        sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\nservices:\n  my-db: { kind: postgresql }\n"
        )

        with pytest.raises(ValueError, match=r"services\.my-db.*template identifier"):
            load_sandbox_config(None)

    def test_load_grpc_kind_fails_not_supported_yet(self, sandbox_yaml):
        """Scenario 14: the grpc kind fails with the explicit 'not supported yet' error."""
        sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\nservices:\n  broker: { kind: grpc }\n"
        )

        with pytest.raises(ValueError, match=r"grpc.*not supported yet"):
            load_sandbox_config(None)

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

        config = load_sandbox_config(None)

        assert config.instance.probe.timeout == 30.0
        assert config.instance.probe.interval == 0.5
        assert config.instance.probe.path is None
        assert config.services["db"].probe.timeout == 45.0
        assert config.services["db"].probe.interval == 0.5

    def test_load_returns_validated_model_for_full_document(self, sandbox_yaml):
        """The full authoring example loads into a validated model with inline topics."""
        sandbox_yaml(FULL_DOCUMENT)

        config = load_sandbox_config(None)

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
            load_sandbox_config(None)

    def test_load_fails_missing_instance_section(self, sandbox_yaml):
        """A document without the instance entry fails naming the entry."""
        sandbox_yaml("services:\n  db: { kind: postgresql }\n")

        with pytest.raises(ValueError, match=r"sandbox\.yml.*instance"):
            load_sandbox_config(None)

    def test_load_fails_unknown_service_kind(self, sandbox_yaml):
        """A kind outside the four supported ones fails listing them."""
        sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\nservices:\n  cache: { kind: redis }\n"
        )

        with pytest.raises(ValueError, match=r"redis.*postgresql.*kafka.*vault.*http"):
            load_sandbox_config(None)

    def test_load_fails_data_targeting_unknown_service(self, sandbox_yaml):
        """A data declaration targeting an unconfigured service fails naming the target."""
        sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\n"
            "services:\n  db: { kind: postgresql }\n"
            'data:\n  postgres:\n    nodb:\n      - "CREATE TABLE orders (id int)"\n'
        )

        with pytest.raises(ValueError, match=r"nodb"):
            load_sandbox_config(None)

    def test_load_fails_data_targeting_service_of_wrong_kind(self, sandbox_yaml):
        """A data section targeting a service of another kind fails naming both kinds."""
        sandbox_yaml(
            "instance:\n  image: my-service:latest\n  port: 8080\n  env: {}\n"
            "services:\n  events: { kind: kafka, topics: [{name: orders.events}] }\n"
            'data:\n  postgres:\n    events:\n      - "CREATE TABLE orders (id int)"\n'
        )

        with pytest.raises(ValueError, match=r"events.*kafka.*postgresql"):
            load_sandbox_config(None)

    def test_load_fails_unparsable_yaml(self, sandbox_yaml):
        """An unparsable document fails naming the location and carrying the parse problem."""
        path = sandbox_yaml(":\n - [")

        with pytest.raises(ValueError, match=r"sandbox\.yml") as excinfo:
            load_sandbox_config(str(path))

        assert str(path) in str(excinfo.value)
        assert "unparsable" in str(excinfo.value)

    def test_load_fails_empty_document(self, sandbox_yaml):
        """A zero-byte document is an invalid document — the error names the location."""
        sandbox_yaml("")

        with pytest.raises(ValueError, match=r"sandbox\.yml"):
            load_sandbox_config(None)

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
                r"data\.cache.*unknown data section.*vault, http, postgres",
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
            load_sandbox_config(None)

    @pytest.mark.parametrize(
        "name",
        ["my-db", "1db", "db.two", "events!"],
    )
    def test_load_fails_service_name_that_is_not_a_template_identifier(self, sandbox_yaml, name):
        """Service names double as Jinja2 placeholder identifiers — anything else fails."""
        sandbox_yaml(f"instance:\n  image: i\n  port: 1\n  env: {{}}\nservices:\n  {name}: {{ kind: postgresql }}\n")

        with pytest.raises(ValueError, match=rf"services\.{re.escape(name)}.*template identifier"):
            load_sandbox_config(None)

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
            load_sandbox_config(None)

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
            load_sandbox_config(None)

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
            load_sandbox_config(None)

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
            load_sandbox_config(None)

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
        ],
    )
    def test_load_fails_on_unknown_or_malformed_entry_keys(self, sandbox_yaml, document, match):
        """A mistyped entry key (``imag`` for ``image``) fails at load instead of silently
        dropping the declaration; a health path without the leading slash fails the same way."""
        sandbox_yaml(document)

        with pytest.raises(ValueError, match=match):
            load_sandbox_config(None)

    @pytest.mark.parametrize("name", ["true", "false", "none", "True", "None"])
    def test_load_fails_on_jinja_literal_service_names(self, sandbox_yaml, name):
        """The Jinja2 literal names parse as constants, not variables — placeholders over them
        could never resolve, so the names are rejected with the identifier-grammar error.
        The name is quoted so YAML hands the loader a string, not a native bool or null."""
        sandbox_yaml(f"instance:\n  image: i\n  port: 1\n  env: {{}}\nservices:\n  '{name}': {{ kind: postgresql }}\n")

        with pytest.raises(ValueError, match=rf"services\.{name}.*template identifier"):
            load_sandbox_config(None)

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
            load_sandbox_config(None)
