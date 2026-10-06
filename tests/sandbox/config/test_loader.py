"""Contract and logic tests for the ``load_sandbox_config`` routine."""

import inspect
import re

import pytest
from goga_tool_pybuggy.sandbox.config import SandboxConfig, load_sandbox_config

FULL_DOCUMENT = """\
service:
  image: my-service:latest
  port: 8080
  health: /health
  env:
    DATABASE_URL: "postgres://{{db.host}}:{{db.port}}/app"
    KAFKA_BOOTSTRAP: "{{events.host}}:{{events.port}}"
    VAULT_ADDR: "http://{{secrets.host}}:{{secrets.port}}"

instances:
  db:       { kind: postgresql, image: postgres:16-alpine }
  events:   { kind: kafka }
  secrets:  { kind: vault }
  payments: { kind: http }

data:
  vault:
    secrets:
      - { path: "payment/api-key", data: { api_key: "test-key", ttl: "1h" } }
  http:
    payments:
      - request:  { method: POST, urlPath: /v1/charge }
        response: { status: 200, jsonBody: { status: "captured" } }
  kafka:
    events: "asyncapi.yaml"
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

    def test_load_returns_validated_model_for_full_document(self, sandbox_yaml, tmp_path):
        """The full authoring example loads into a validated model with the kafka spec resolved."""
        path = sandbox_yaml(FULL_DOCUMENT)

        config = load_sandbox_config(str(path))

        assert isinstance(config, SandboxConfig)
        assert config.service.image == "my-service:latest"
        assert config.service.port == 8080
        assert config.service.health == "/health"
        assert config.service.env["DATABASE_URL"] == "postgres://{{db.host}}:{{db.port}}/app"
        assert config.service.env["KAFKA_BOOTSTRAP"] == "{{events.host}}:{{events.port}}"
        assert config.service.env["VAULT_ADDR"] == "http://{{secrets.host}}:{{secrets.port}}"
        assert set(config.instances) == {"db", "events", "secrets", "payments"}
        assert config.instances["db"].kind == "postgresql"
        assert config.instances["db"].image == "postgres:16-alpine"
        assert config.instances["events"].image is None
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
        assert config.data.kafka == {"events": str(tmp_path / "asyncapi.yaml")}
        assert config.data.postgres == {
            "db": ["CREATE TABLE IF NOT EXISTS orders (id bigint PRIMARY KEY, customer text, total numeric)"]
        }

    def test_load_returns_none_without_document(self, tmp_path, monkeypatch):
        """An absent document leaves the sandbox fully inert — None, no error."""
        monkeypatch.chdir(tmp_path)

        assert load_sandbox_config(None) is None

    def test_load_fails_grpc_kind_with_not_supported_yet(self, sandbox_yaml):
        """The grpc kind fails with the explicit 'not supported yet' error."""
        sandbox_yaml(
            "service:\n  image: my-service:latest\n  port: 8080\n  env: {}\ninstances:\n  broker: { kind: grpc }\n"
        )

        with pytest.raises(ValueError, match=r"grpc.*not supported yet"):
            load_sandbox_config(None)

    def test_load_fails_unknown_env_placeholder_before_start(self, sandbox_yaml):
        """A placeholder naming an unconfigured instance fails before anything starts."""
        sandbox_yaml(
            "service:\n"
            "  image: my-service:latest\n"
            "  port: 8080\n"
            "  env:\n"
            '    DATABASE_URL: "postgres://{{ghost.host}}:5432/app"\n'
            "instances:\n"
            "  db: { kind: postgresql }\n"
        )

        with pytest.raises(ValueError, match=r"DATABASE_URL.*ghost"):
            load_sandbox_config(None)

    def test_load_fails_bare_instance_placeholder(self, sandbox_yaml):
        """A bare instance name without the host/port attribute fails naming the env key."""
        sandbox_yaml(
            "service:\n"
            "  image: my-service:latest\n"
            "  port: 8080\n"
            "  env:\n"
            '    KAFKA_BOOTSTRAP: "{{events}}"\n'
            "instances:\n"
            "  events: { kind: kafka }\n"
        )

        with pytest.raises(ValueError, match=r"KAFKA_BOOTSTRAP.*events"):
            load_sandbox_config(None)

    def test_load_fails_unknown_placeholder_attribute(self, sandbox_yaml):
        """A placeholder attribute outside host/port fails naming the env key and the attribute."""
        sandbox_yaml(
            "service:\n"
            "  image: my-service:latest\n"
            "  port: 8080\n"
            "  env:\n"
            '    DATABASE_URL: "{{db.hst}}"\n'
            "instances:\n"
            "  db: { kind: postgresql }\n"
        )

        with pytest.raises(ValueError, match=r"DATABASE_URL.*hst"):
            load_sandbox_config(None)

    def test_load_fails_data_targeting_unknown_instance(self, sandbox_yaml):
        """A data declaration targeting an unconfigured instance fails naming the target."""
        sandbox_yaml(
            "service:\n"
            "  image: my-service:latest\n"
            "  port: 8080\n"
            "  env: {}\n"
            "instances:\n"
            "  db: { kind: postgresql }\n"
            "data:\n"
            "  postgres:\n"
            "    nodb:\n"
            '      - "CREATE TABLE orders (id int)"\n'
        )

        with pytest.raises(ValueError, match=r"nodb"):
            load_sandbox_config(None)

    def test_load_fails_data_targeting_instance_of_wrong_kind(self, sandbox_yaml):
        """A data section targeting an instance of another kind fails naming both kinds."""
        sandbox_yaml(
            "service:\n"
            "  image: my-service:latest\n"
            "  port: 8080\n"
            "  env: {}\n"
            "instances:\n"
            "  events: { kind: kafka }\n"
            "data:\n"
            "  postgres:\n"
            "    events:\n"
            '      - "CREATE TABLE orders (id int)"\n'
        )

        with pytest.raises(ValueError, match=r"events.*kafka.*postgresql"):
            load_sandbox_config(None)

    def test_load_fails_unknown_instance_kind(self, sandbox_yaml):
        """A kind outside the four supported ones fails listing them."""
        sandbox_yaml(
            "service:\n  image: my-service:latest\n  port: 8080\n  env: {}\ninstances:\n  cache: { kind: redis }\n"
        )

        with pytest.raises(ValueError, match=r"redis.*postgresql.*kafka.*vault.*http"):
            load_sandbox_config(None)

    def test_load_fails_missing_required_service_field(self, sandbox_yaml):
        """A missing required service field fails naming the field."""
        sandbox_yaml("service:\n  image: my-service:latest\n  env: {}\n")

        with pytest.raises(ValueError, match=r"service\.port"):
            load_sandbox_config(None)

    def test_load_fails_missing_service_section(self, sandbox_yaml):
        """A document without the service entry fails naming the entry."""
        sandbox_yaml("instances:\n  db: { kind: postgresql }\n")

        with pytest.raises(ValueError, match=r"\.sandbox\.yml.*service"):
            load_sandbox_config(None)

    def test_load_fails_unparsable_yaml(self, sandbox_yaml):
        """An unparsable document fails naming the location and carrying the parse problem."""
        path = sandbox_yaml(":\n - [")

        with pytest.raises(ValueError, match=r"\.sandbox\.yml") as excinfo:
            load_sandbox_config(str(path))

        assert str(path) in str(excinfo.value)
        assert "unparsable" in str(excinfo.value)

    def test_load_fails_empty_document(self, sandbox_yaml):
        """A zero-byte document is an invalid document — the error names the location."""
        sandbox_yaml("")

        with pytest.raises(ValueError, match=r"\.sandbox\.yml"):
            load_sandbox_config(None)

    @pytest.mark.parametrize(
        ("document", "match"),
        [
            ("service:\n  image: i\n  port: 1\n  env: {}\ninstances: []", r"instances.*mapping"),
            (
                "service:\n  image: i\n  port: 1\n  env: {}\ninstances:\n  ' ': { kind: postgresql }",
                r"instances.*non-empty string",
            ),
            (
                "service:\n  image: i\n  port: 1\n  env: {}\ninstances:\n  db: oops",
                r"instances\.db.*mapping",
            ),
            (
                "service:\n  image: i\n  port: 1\n  env: {}\ninstances:\n  db: { image: x }",
                r"instances\.db\.kind.*missing",
            ),
            (
                "service:\n  image: i\n  port: 1\n  env: {}\ninstances:\n  db: { kind: }\n",
                r"instances\.db\.kind.*missing",
            ),
            ("service:\n  image: i\n  port: 1\n  env: {}\ninstances: {}\ndata: []", r"data.*mapping"),
            (
                "service:\n  image: i\n  port: 1\n  env: {}\ninstances:\n  db: { kind: postgresql }\n"
                "data:\n  postgres: oops",
                r"data\.postgres.*mapping",
            ),
            (
                "service:\n  image: i\n  port: 1\n  env: {}\ninstances: {}\ndata:\n  cache: {}",
                r"data\.cache.*unknown data section.*vault, http, kafka, postgres",
            ),
            (
                "service:\n  image: i\n  port: 1\n  env: {}\ninstances:\n  events: { kind: kafka }\n"
                "data:\n  kafka:\n    events: 7",
                r"data\.kafka\.events.*non-empty string",
            ),
            (
                "service:\n  image: i\n  port: [1]\n  env: {}\ninstances: {}",
                r"service.*port.*Input should be a valid integer",
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
    def test_load_fails_instance_name_that_is_not_a_template_identifier(self, sandbox_yaml, name):
        """Instance names double as Jinja2 placeholder identifiers — anything else fails."""
        sandbox_yaml(f"service:\n  image: i\n  port: 1\n  env: {{}}\ninstances:\n  {name}: {{ kind: postgresql }}\n")

        with pytest.raises(ValueError, match=rf"instances\.{re.escape(name)}.*template identifier"):
            load_sandbox_config(None)

    def test_load_fails_unterminated_placeholder_in_env_value(self, sandbox_yaml):
        """An env value with an unterminated ``{{`` fails at load time, not at render time."""
        sandbox_yaml(
            "service:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env:\n"
            '    DATABASE_URL: "postgres://{{db.host:5432/app"\n'
            "instances:\n"
            "  db: { kind: postgresql }\n"
        )

        with pytest.raises(ValueError, match=r"DATABASE_URL.*unterminated.*'\{\{'"):
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
            "service:\n"
            "  image: i\n"
            "  port: 1\n"
            "  env: {}\n"
            "instances:\n"
            "  secrets: { kind: vault }\n"
            "data:\n"
            "  vault:\n"
            f"    secrets:\n      {declaration}\n"
        )

        with pytest.raises(ValueError, match=match):
            load_sandbox_config(None)
