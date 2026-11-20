"""Tests for the nine bootstrap writers — contract surface, round-trip guarantees, deltas.

Covers the writers relocated from the 1.x ``init.py``, the two migration deltas, the 2.0.1
restoration, the web-kind documenter/playwright writers, and the ``run_bootstrap`` packaged-usage
distribution over the sandbox subtree.
"""

import importlib.metadata
import importlib.resources
import logging
from pathlib import Path

import click
import pytest
import yaml
from goga_tool_pybuggy.commands.init import (
    document_config_examples,
    document_web_config_examples,
    ensure_review_skip,
    install_playwright,
    install_pybuggy,
    register_annotations,
    register_usages,
    run_bootstrap,
    write_pybuggy_conftest,
    write_test_convention,
)
from goga_tool_pybuggy.plugins import PluginConfigKeys
from ruamel.yaml import YAML

_EXPECTED_CONFTEST = (
    "from dotenv import load_dotenv\n\nload_dotenv()\n\nfrom goga_tool_pybuggy import plugins\n\nplugins.install()\n"
)

# The exact first lines the documentation step re-delivers for absent complex members.
_HEADERS_FIRST_LINE = "headers: example (skipped complex member)"
_LOADER_FIRST_LINE = "loader: example (skipped complex member)"

_USAGE_INPUT = {"pybuggy-api": "new.md", "conventions": ".goga/usages/conventions.md"}

_ANNOTATION_INPUT = {
    "pybuggy-api": "Use `pybuggy-api` for executing HTTP requests from test fixtures.",
    "conventions": "Use `conventions` for test code: pytest configuration, logging, and Allure reporting.",
}

# The install block the bootstrap writes into the consumer Dockerfile — the root-user project-copy
# install step; the bulk ``goga install`` reads the project's ``tools:`` pin, so no version lives here.
_INSTALL_BLOCK = "USER root\nCOPY . /tmp/project\nRUN cd /tmp/project && goga install && rm -rf /tmp/project\nUSER goga"

# The packaged usage texts the bootstrap distributes — the api root (incl. ``asserts``), the
# sandbox subtree, and the web root; stems are unique across the three roots.
_API_PACKAGE = importlib.resources.files("goga_tool_pybuggy.api")
_SANDBOX_PACKAGE = importlib.resources.files("goga_tool_pybuggy.sandbox")
_WEB_PACKAGE = importlib.resources.files("goga_tool_pybuggy.web")
_PACKAGED_USAGES = {
    "api": (_API_PACKAGE / ".usages" / "api.md").read_text(encoding="utf-8"),
    "asserts": (_API_PACKAGE / "asserts" / ".usages" / "asserts.md").read_text(encoding="utf-8"),
    "sandbox-session": (_SANDBOX_PACKAGE / ".usages" / "sandbox-session.md").read_text(encoding="utf-8"),
    "sandbox-file": (_SANDBOX_PACKAGE / "config" / ".usages" / "sandbox-file.md").read_text(encoding="utf-8"),
    "data-operations": (_SANDBOX_PACKAGE / "data" / ".usages" / "data-operations.md").read_text(encoding="utf-8"),
    "migration-set": (_SANDBOX_PACKAGE / "migrations" / ".usages" / "migration-set.md").read_text(encoding="utf-8"),
    "pybuggy-web": (_WEB_PACKAGE / ".usages" / "pybuggy-web.md").read_text(encoding="utf-8"),
}

# The four sandbox stems — download-only: copied as files, never registered in the consumer config.
_SANDBOX_STEMS = ("sandbox-session", "sandbox-file", "data-operations", "migration-set")


def _seed_bootstrap_target(root: Path) -> None:
    """Seed a minimal bootstrappable consumer project — config plus the declared Dockerfile.

    Args:
        root: The scratch project root (the test's ``tmp_path``).
    """
    goga = root / ".goga"
    goga.mkdir(exist_ok=True)
    (goga / "config.yml").write_text("language: python\ndockerfile: Dockerfile\n", encoding="utf-8")
    (root / "Dockerfile").write_text("FROM x\n", encoding="utf-8")


def _seed_api_config(root: Path) -> None:
    """Seed the api kind signal — a written ``api.yml`` tool config.

    Args:
        root: The scratch project root (the test's ``tmp_path``).
    """
    api_config = root / ".goga" / "tools" / "pybuggy" / "api.yml"
    api_config.parent.mkdir(parents=True, exist_ok=True)
    api_config.write_text(
        "base_url: https://{{ HOST }}/api\nspecs:\n  shop:\n    type: swagger\n    location: specs/shop.yaml\n",
        encoding="utf-8",
    )


def _seed_web_config(root: Path) -> None:
    """Seed the web kind signal — a written ``web.yml`` tool config.

    Args:
        root: The scratch project root (the test's ``tmp_path``).
    """
    web_config = root / ".goga" / "tools" / "pybuggy" / "web.yml"
    web_config.parent.mkdir(parents=True, exist_ok=True)
    web_config.write_text(
        "provider: openai\ngeneration_model: g\nclassification_model: c\n"
        "browser:\n  name: chromium\n  headless: true\nstrict: false\ninteractive: false\n",
        encoding="utf-8",
    )


class TestBootstrapContract:
    """Facade exposure and signature surface of the nine bootstrap writers."""

    def test_facade_exports_nine_bootstrap_writers(self):
        """All nine writer routines are importable from the cell facade."""
        assert callable(ensure_review_skip)
        assert callable(install_pybuggy)
        assert callable(install_playwright)
        assert callable(register_usages)
        assert callable(register_annotations)
        assert callable(write_pybuggy_conftest)
        assert callable(write_test_convention)
        assert callable(document_config_examples)
        assert callable(document_web_config_examples)

    @pytest.mark.parametrize(
        ("routine", "expected"),
        [
            (write_test_convention, {"path": Path, "return": None}),
            (ensure_review_skip, {"config_path": Path, "return": bool}),
            (install_pybuggy, {"dockerfile_path": Path, "return": str | None}),
            (install_playwright, {"dockerfile_path": Path, "return": str | None}),
            (register_usages, {"config_path": Path, "usage_keys": dict[str, str], "return": list[str]}),
            (register_annotations, {"config_path": Path, "annotation_lines": dict[str, str], "return": list[str]}),
            (write_pybuggy_conftest, {"path": Path, "return": None}),
            (document_config_examples, {"config_path": Path, "return": list[str]}),
            (document_web_config_examples, {"config_path": Path, "return": list[str]}),
        ],
    )
    def test_writer_signature_matches_contract(self, routine, expected):
        """Every writer carries its contract signature with typed parameters and return."""
        assert routine.__annotations__ == expected


class TestEnsureReviewSkip:
    """``build.review.skip`` enforcement with round-trip preservation."""

    def test_ensure_review_skip_enforces_key_and_preserves_config(self, tmp_path, caplog):
        """The new key lands, comments and siblings survive, and a repeat run never writes."""
        config = tmp_path / "config.yml"
        config.write_text(
            "# keep me\nlanguage: python\nbuild:\n  task_executor:  # sibling stays\n    agent: swax\n",
            encoding="utf-8",
        )

        with caplog.at_level(logging.INFO):
            assert ensure_review_skip(config) is True

        assert "review executor skip enabled" in caplog.text
        yaml = YAML()
        data = yaml.load(config)
        assert data["build"]["review"]["skip"] is True
        assert data["build"]["task_executor"] == {"agent": "swax"}
        assert "# keep me" in config.read_text(encoding="utf-8")
        assert "# sibling stays" in config.read_text(encoding="utf-8")

        first_bytes = config.read_bytes()
        mtime = config.stat().st_mtime_ns
        assert ensure_review_skip(config) is False
        assert config.read_bytes() == first_bytes
        assert config.stat().st_mtime_ns == mtime

    @pytest.mark.parametrize(
        "config_text",
        [
            pytest.param("build:\n  review:\n    skip: false\n", id="explicit-false"),
            pytest.param("build:\n  review:\n    skip: maybe\n", id="non-boolean-string"),
        ],
    )
    def test_ensure_review_skip_corrects_a_present_non_true_value(self, tmp_path, config_text):
        """A present false (or non-boolean) skip value is corrected to true."""
        config = tmp_path / "config.yml"
        config.write_text(config_text, encoding="utf-8")

        assert ensure_review_skip(config) is True
        assert YAML().load(config)["build"]["review"]["skip"] is True


class TestNeverOverwriteGuards:
    """The never-overwrite guards — a non-conforming section raises instead of clobbering."""

    @pytest.mark.parametrize(
        ("config_text", "writer"),
        [
            pytest.param("build: scalar\n", ensure_review_skip, id="build-not-a-mapping"),
            pytest.param("build:\n  review: [list]\n", ensure_review_skip, id="review-not-a-mapping"),
            pytest.param(
                "codemanifest: [a, b]\n",
                lambda config: register_usages(config, _USAGE_INPUT),
                id="codemanifest-not-a-mapping",
            ),
            pytest.param(
                "codemanifest:\n  usages: scalar\n",
                lambda config: register_usages(config, _USAGE_INPUT),
                id="usages-not-a-mapping",
            ),
            pytest.param(
                "codemanifest:\n  annotations: {k: v}\n",
                lambda config: register_annotations(config, _ANNOTATION_INPUT),
                id="annotations-not-a-scalar",
            ),
        ],
    )
    def test_non_conforming_section_raises_and_keeps_file_unchanged(self, tmp_path, config_text, writer):
        """A non-mapping/non-scalar guarded section raises ValueError and leaves the file untouched."""
        config = tmp_path / "config.yml"
        config.write_text(config_text, encoding="utf-8")
        before = config.read_bytes()

        with pytest.raises(ValueError, match="cannot be extended"):
            writer(config)

        assert config.read_bytes() == before


class TestInstallPybuggy:
    """The root-user project-copy install block — write, stale-line replacement, idempotency."""

    def test_install_pybuggy_writes_the_root_install_block_and_is_idempotent(self, tmp_path, caplog):
        """The block appends once, then no-ops at the current block."""
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM qarium/goga-python-3.14:2.0\n", encoding="utf-8")

        with caplog.at_level(logging.INFO):
            block = install_pybuggy(dockerfile)

        assert block == _INSTALL_BLOCK
        assert dockerfile.read_text(encoding="utf-8") == f"FROM qarium/goga-python-3.14:2.0\n{_INSTALL_BLOCK}\n"
        assert "pybuggy install block added to Dockerfile" in caplog.text

        assert install_pybuggy(dockerfile) is None
        assert dockerfile.read_text(encoding="utf-8") == f"FROM qarium/goga-python-3.14:2.0\n{_INSTALL_BLOCK}\n"

    def test_install_pybuggy_ensures_newline_separator(self, tmp_path):
        """A Dockerfile without a trailing newline still gets the block on fresh lines."""
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM qarium/goga-python-3.14:2.0", encoding="utf-8")

        assert install_pybuggy(dockerfile) == _INSTALL_BLOCK
        assert dockerfile.read_text(encoding="utf-8") == f"FROM qarium/goga-python-3.14:2.0\n{_INSTALL_BLOCK}\n"

    @pytest.mark.parametrize(
        "stale", ["RUN goga install pybuggy -v 2.0", "RUN goga install pybuggy -v 2.0.x"], ids=["concrete", "x-range"]
    )
    def test_install_pybuggy_replaces_a_stale_install_line_instead_of_appending(self, stale, tmp_path, caplog):
        """A single install line of any previous release shape is replaced by the block, never joined."""
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text(f"FROM qarium/goga-python-3.14:2.0\n{stale}\n", encoding="utf-8")

        with caplog.at_level(logging.INFO):
            block = install_pybuggy(dockerfile)

        assert block == _INSTALL_BLOCK
        assert dockerfile.read_text(encoding="utf-8") == f"FROM qarium/goga-python-3.14:2.0\n{_INSTALL_BLOCK}\n"
        assert "pybuggy install block replaced in Dockerfile" in caplog.text
        assert dockerfile.read_text(encoding="utf-8").count("goga install") == 1

        assert install_pybuggy(dockerfile) is None
        assert dockerfile.read_text(encoding="utf-8") == f"FROM qarium/goga-python-3.14:2.0\n{_INSTALL_BLOCK}\n"

    def test_install_pybuggy_noop_without_file(self, tmp_path):
        """An absent Dockerfile is a no-op — the file is never created."""
        absent = tmp_path / "Dockerfile"

        assert install_pybuggy(absent) is None
        assert not absent.exists()

    def test_install_pybuggy_derives_nothing_from_the_installed_version(self, tmp_path, monkeypatch):
        """The block carries no version pin — a metadata-less run writes it all the same."""

        def _missing(name: str) -> str:
            raise importlib.metadata.PackageNotFoundError(name)

        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM qarium/goga-python-3.14:2.0\n", encoding="utf-8")
        monkeypatch.setattr(importlib.metadata, "version", _missing)

        assert install_pybuggy(dockerfile) == _INSTALL_BLOCK
        assert "-v " not in dockerfile.read_text(encoding="utf-8")


class TestInstallPlaywright:
    """The browser install line — root-section anchor, relocation, lenient config reads."""

    def test_install_playwright_inserts_inside_the_root_section(self, tmp_path, monkeypatch):
        """The line lands between the install RUN and the block-closing USER goga, exactly once."""
        monkeypatch.chdir(tmp_path)
        tools = tmp_path / ".goga" / "tools" / "pybuggy"
        tools.mkdir(parents=True)
        (tools / "web.yml").write_text("browser: {name: chromium}\n", encoding="utf-8")
        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text(f"FROM base\n{_INSTALL_BLOCK}\n", encoding="utf-8")
        expected = (
            "FROM base\nUSER root\nCOPY . /tmp/project\n"
            "RUN cd /tmp/project && goga install && rm -rf /tmp/project\n"
            "RUN playwright install --with-deps chromium\nUSER goga\n"
        )

        assert install_playwright(dockerfile) == "RUN playwright install --with-deps chromium"
        assert dockerfile.read_text(encoding="utf-8") == expected

        snapshot = dockerfile.read_bytes()
        assert install_playwright(dockerfile) is None
        assert dockerfile.read_bytes() == snapshot

        # The inserted line does not defeat install_pybuggy's idempotency — the block-present
        # check keys on the install RUN line, whatever sits inside the block.
        assert install_pybuggy(dockerfile) is None
        assert dockerfile.read_bytes() == snapshot

        (tools / "web.yml").write_text("browser: {name: firefox}\n", encoding="utf-8")

        assert install_playwright(dockerfile) == "RUN playwright install --with-deps firefox"
        content = dockerfile.read_text(encoding="utf-8")
        assert content.count("RUN playwright install") == 1
        assert content == expected.replace("chromium", "firefox")

    def test_install_playwright_relocates_a_stranded_line(self, tmp_path, monkeypatch):
        """A playwright line left outside the root section (the pre-fix layout) moves inside it."""
        monkeypatch.chdir(tmp_path)
        tools = tmp_path / ".goga" / "tools" / "pybuggy"
        tools.mkdir(parents=True)
        (tools / "web.yml").write_text("browser: {name: chromium}\n", encoding="utf-8")
        dockerfile = tmp_path / "Dockerfile"
        stranded = f"FROM base\n{_INSTALL_BLOCK}\nRUN playwright install --with-deps chromium\n"
        dockerfile.write_text(stranded, encoding="utf-8")

        assert install_playwright(dockerfile) == "RUN playwright install --with-deps chromium"
        assert dockerfile.read_text(encoding="utf-8") == (
            "FROM base\nUSER root\nCOPY . /tmp/project\n"
            "RUN cd /tmp/project && goga install && rm -rf /tmp/project\n"
            "RUN playwright install --with-deps chromium\nUSER goga\n"
        )

        assert install_playwright(dockerfile) is None

    def test_install_playwright_noop_paths(self, tmp_path, monkeypatch, caplog):
        """Absent Dockerfile, absent/unreadable web config, and a newline-less Dockerfile all behave."""
        monkeypatch.chdir(tmp_path)
        tools = tmp_path / ".goga" / "tools" / "pybuggy"
        tools.mkdir(parents=True)

        absent = tmp_path / "Dockerfile"
        assert install_playwright(absent) is None
        assert not absent.exists()

        dockerfile = tmp_path / "Dockerfile"
        dockerfile.write_text("FROM base\n", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            assert install_playwright(dockerfile) is None

        assert "web config unreadable" in caplog.text
        assert dockerfile.read_text(encoding="utf-8") == "FROM base\n"

        caplog.clear()
        (tools / "web.yml").write_text("provider: [unclosed\n", encoding="utf-8")

        with caplog.at_level(logging.WARNING):
            assert install_playwright(dockerfile) is None

        assert "web config unreadable" in caplog.text

        # A readable document without a usable browser name — no browser key, then an empty name —
        # is the same lenient no-op.
        for document in ("provider: openai\n", "browser: {name: ''}\n"):
            (tools / "web.yml").write_text(document, encoding="utf-8")
            caplog.clear()

            with caplog.at_level(logging.WARNING):
                assert install_playwright(dockerfile) is None

            assert "web config unreadable" in caplog.text
            assert dockerfile.read_text(encoding="utf-8") == "FROM base\n"

        (tools / "web.yml").write_text("browser:\n  name: chromium\n", encoding="utf-8")
        dockerfile.write_text("FROM base", encoding="utf-8")

        assert install_playwright(dockerfile) == "RUN playwright install --with-deps chromium"
        assert dockerfile.read_text(encoding="utf-8") == "FROM base\nRUN playwright install --with-deps chromium\n"

        # The defensive end-of-file append also honors an existing trailing newline.
        dockerfile.write_text("FROM base\n", encoding="utf-8")

        assert install_playwright(dockerfile) == "RUN playwright install --with-deps chromium"
        assert dockerfile.read_text(encoding="utf-8") == "FROM base\nRUN playwright install --with-deps chromium\n"


class TestDocumentConfigExamples:
    """The commented example records — the 1.x option surface restored post-session."""

    def test_document_adds_records_in_key_order_with_specs_anchor(self, tmp_path):
        """Absent members land as commented records pinned before the next active key / specs."""
        config = tmp_path / "config.yml"
        config.write_text(
            "base_url: https://{{ HOST }}/api\ntimeout: 30.0\nspecs:\n"
            "  shop:\n    type: swagger\n    location: specs/shop.yaml\n",
            encoding="utf-8",
        )

        documented = document_config_examples(config)

        assert [record.split("\n", 1)[0] for record in documented] == [
            _HEADERS_FIRST_LINE,
            "retries: (skipped optional scalar)",
            _LOADER_FIRST_LINE,
            "assert_timeout: (skipped optional scalar)",
            "assert_delay: (skipped optional scalar)",
            "assert_field_class: (skipped optional scalar)",
            "assert_response_class: (skipped optional scalar)",
        ]
        text = config.read_text(encoding="utf-8")
        assert text == (
            "base_url: https://{{ HOST }}/api\n"
            f"# {_HEADERS_FIRST_LINE}\n"
            "#   X-Example: value\n"
            "#   default request headers dict\n"
            "timeout: 30.0\n"
            "# retries: (skipped optional scalar)\n"
            f"# {_LOADER_FIRST_LINE}\n"
            "#   packages:\n"
            "#     - api\n"
            "#   modules: []\n"
            "# assert_timeout: (skipped optional scalar)\n"
            "# assert_delay: (skipped optional scalar)\n"
            "# assert_field_class: (skipped optional scalar)\n"
            "# assert_response_class: (skipped optional scalar)\n"
            "specs:\n"
            "  shop:\n"
            "    type: swagger\n"
            "    location: specs/shop.yaml\n"
        )

    def test_document_is_idempotent_and_preserves_active_values(self, tmp_path):
        """A repeat run adds nothing, and the active keys keep their values throughout."""
        config = tmp_path / "config.yml"
        config.write_text(
            "base_url: https://{{ HOST }}/api\ntimeout: 30.0\nretries: 3\nspecs:\n"
            "  shop:\n    type: swagger\n    location: specs/shop.yaml\n",
            encoding="utf-8",
        )

        assert document_config_examples(config) != []
        snapshot = config.read_text(encoding="utf-8")

        assert document_config_examples(config) == []
        assert config.read_text(encoding="utf-8") == snapshot

        data = YAML().load(config)
        assert data["timeout"] == 30.0
        assert data["retries"] == 3
        assert data["specs"]["shop"] == {"type": "swagger", "location": "specs/shop.yaml"}
        assert "headers" not in data
        assert "loader" not in data

    def test_document_pins_pending_records_before_midway_active_key(self, tmp_path):
        """Records accumulate only up to the next active key — mid-walk anchors split the blocks."""
        config = tmp_path / "config.yml"
        config.write_text(
            "base_url: https://x\nretries: 3\nspecs:\n  shop:\n    type: swagger\n    location: s.yaml\n",
            encoding="utf-8",
        )

        document_config_examples(config)

        text = config.read_text(encoding="utf-8")
        headers_at = text.index(f"# {_HEADERS_FIRST_LINE}")
        timeout_at = text.index("# timeout: (skipped optional scalar)")
        retries_at = text.index("retries: 3")
        loader_at = text.index(f"# {_LOADER_FIRST_LINE}")
        specs_at = text.index("specs:")
        assert headers_at < timeout_at < retries_at < loader_at < specs_at

    def test_document_active_member_never_gains_a_record(self, tmp_path):
        """A member the user activated (headers hand-added) is documented nowhere."""
        config = tmp_path / "config.yml"
        config.write_text(
            "base_url: https://x\nheaders:\n  X-Api-Key: k\nspecs:\n  shop:\n    type: swagger\n    location: s.yaml\n",
            encoding="utf-8",
        )

        documented = document_config_examples(config)

        assert _HEADERS_FIRST_LINE not in "\n".join(documented)
        assert f"# {_HEADERS_FIRST_LINE}" not in config.read_text(encoding="utf-8")
        assert any(record.startswith("timeout:") for record in documented)

    def test_document_noop_without_file_or_mapping(self, tmp_path):
        """An absent config and a non-mapping document are no-ops."""
        absent = tmp_path / "config.yml"
        assert document_config_examples(absent) == []
        assert not absent.exists()

        scalar = tmp_path / "scalar.yml"
        scalar.write_text("just a string\n", encoding="utf-8")
        assert document_config_examples(scalar) == []
        assert scalar.read_text(encoding="utf-8") == "just a string\n"

    def test_document_marker_matches_the_comment_line_only(self, tmp_path):
        """A sibling's record line is not the key's own marker — ``timeout`` still gets documented.

        ``timeout: (skipped optional scalar)`` is a substring of ``assert_timeout: (skipped
        optional scalar)``; the detection must match the emitted comment line so a file carrying
        the sibling's record (e.g. after a hand edit) does not silently skip the key's own.
        """
        config = tmp_path / "config.yml"
        config.write_text(
            "base_url: https://api.example\n"
            "# assert_timeout: (skipped optional scalar)\n"
            "specs:\n"
            "  shop:\n    type: swagger\n    location: specs/shop.yaml\n",
            encoding="utf-8",
        )

        documented = document_config_examples(config)

        assert "timeout: (skipped optional scalar)" in documented
        text = config.read_text(encoding="utf-8")
        assert "# timeout: (skipped optional scalar)" in text
        # The present sibling record is detected by its own marker — never duplicated.
        assert text.count("assert_timeout: (skipped optional scalar)") == 1

    def test_document_covers_every_plugin_member(self, tmp_path):
        """The walk is data-driven — every PluginConfigKeys member gets its record shape."""
        config = tmp_path / "config.yml"
        config.write_text(
            "base_url: https://x\nspecs:\n  shop:\n    type: swagger\n    location: s.yaml\n", encoding="utf-8"
        )

        document_config_examples(config)

        text = config.read_text(encoding="utf-8")
        for member in PluginConfigKeys:
            if member in (PluginConfigKeys.BASE_URL, PluginConfigKeys.HEADERS, PluginConfigKeys.LOADER):
                continue

            assert f"# {member.value}: (skipped optional scalar)" in text

        assert f"# {_HEADERS_FIRST_LINE}" in text
        assert f"# {_LOADER_FIRST_LINE}" in text
        assert "# base_url:" not in text


class TestDocumentWebConfigExamples:
    """The commented web default records — the option surface the engine serialization does not carry."""

    def test_document_web_config_examples_documents_absent_keys(self, tmp_path):
        """Absent web keys land as commented default records; the second run adds nothing and never touches values."""
        web = tmp_path / "web.yml"
        web.write_text(
            "provider: openai\ngeneration_model: g\nclassification_model: c\nbrowser:\n"
            "  name: chromium\n  headless: true\nstrict: false\ninteractive: false\n",
            encoding="utf-8",
        )

        documented = document_web_config_examples(web)

        # every absent member except the six active ones, plus the six absent browser subkeys
        assert len(documented) == 22
        text = web.read_text(encoding="utf-8")
        assert "# base_url: ''" in text
        assert "# cache_root: ''" in text
        assert "# send_structure: true" in text
        assert "# screen: ''" in text
        assert "# speed: 100" in text
        assert "# ignore_https_errors: false" in text
        assert "# site:\n#   base_url: ''" in text

        snapshot = web.read_bytes()
        assert document_web_config_examples(web) == []
        assert web.read_bytes() == snapshot

        data = YAML().load(web)
        assert data["provider"] == "openai"
        assert data["generation_model"] == "g"
        assert data["classification_model"] == "c"
        assert data["browser"] == {"name": "chromium", "headless": True}
        assert data["strict"] is False
        assert data["interactive"] is False

    def test_document_web_config_examples_records_carry_library_defaults(self, tmp_path):
        """Every record value equals the library default — the model is the single default source."""
        from prettyplay import PrettyConfig

        web = tmp_path / "web.yml"
        web.write_text(
            "provider: openai\ngeneration_model: g\nclassification_model: c\nbrowser:\n"
            "  name: chromium\n  headless: true\nstrict: false\ninteractive: false\n",
            encoding="utf-8",
        )

        documented = document_web_config_examples(web)

        defaults = PrettyConfig().model_dump()
        for record in documented:
            if record.startswith("site:\n"):  # the nested site block — its lines carry the group defaults
                nested = {
                    key: yaml.safe_load(value)
                    for key, _, value in (line.strip().partition(": ") for line in record.splitlines()[1:])
                }

                assert nested == defaults["site"], record
                continue

            key, _, value = record.partition(": ")
            expected = defaults["browser"][key] if key in defaults["browser"] else defaults[key]

            assert yaml.safe_load(value) == expected, record

    def test_document_web_config_examples_uncommented_records_are_valid_active_keys(self, tmp_path):
        """Uncommenting every documented line yields a valid document of exactly the defaults.

        The user-facing contract of the records: an uncommented line is a working active key — the
        nested browser lines land inside the browser mapping at its own indentation.
        """
        web = tmp_path / "web.yml"
        web.write_text(
            "provider: openai\ngeneration_model: g\nclassification_model: c\nbrowser:\n"
            "  name: chromium\n  headless: true\nstrict: false\ninteractive: false\n",
            encoding="utf-8",
        )

        document_web_config_examples(web)

        uncommented = "\n".join(
            ("  " + line[4:] if line.startswith("  # ") else line[2:] if line.startswith("# ") else line)
            for line in web.read_text(encoding="utf-8").splitlines()
        )
        data = yaml.safe_load(uncommented)
        assert data["polling_delay"] == 0.5
        assert data["polling_timeout"] is None
        assert data["request_max_tokens"] == 16384
        assert data["generation_approve"] is True
        assert data["cache_root"] == ""
        assert data["browser"]["screen"] == ""
        assert data["browser"]["endpoint"] == ""
        assert data["browser"]["accept_dialogs"] is False
        assert data["browser"]["speed"] == 100
        assert data["browser"]["timeout"] == 30
        # the surveyed values survive the uncommenting — records never overwrite active keys
        assert data["provider"] == "openai"
        assert data["browser"]["name"] == "chromium"
        assert data["browser"]["headless"] is True

    def test_document_web_config_examples_pins_before_next_active_key(self, tmp_path):
        """Records land in walk order pinned before the next active key — browser is the terminal anchor."""
        web = tmp_path / "web.yml"
        web.write_text(
            "provider: openai\ngeneration_model: g\nclassification_model: c\nbrowser:\n"
            "  name: chromium\n  headless: true\nstrict: false\ninteractive: false\n",
            encoding="utf-8",
        )

        document_web_config_examples(web)

        text = web.read_text(encoding="utf-8")
        assert text.index("# base_url: ''") < text.index("generation_model:")
        assert text.index("# model: ''") < text.index("generation_model:")
        assert text.index("# generation_prompt: ''") < text.index("strict:")
        assert text.index("# classification_prompt: ''") < text.index("strict:")
        assert text.index("# generation_attempts: 3") < text.index("browser:")
        assert text.index("# cache_root: ''") < text.index("browser:")
        # the nested records sit inside the browser block, above its last active key
        assert text.index("browser:") < text.index("  # screen: ''") < text.index("  headless: true")

    def test_document_web_config_examples_noop_when_absent_or_non_mapping(self, tmp_path):
        """An absent web config and a non-mapping document are no-ops — the file is never created."""
        absent = tmp_path / "web.yml"
        assert document_web_config_examples(absent) == []
        assert not absent.exists()

        listed = tmp_path / "list.yml"
        listed.write_text("- a\n- b\n", encoding="utf-8")
        assert document_web_config_examples(listed) == []
        assert listed.read_text(encoding="utf-8") == "- a\n- b\n"

    def test_document_web_config_examples_skips_nested_of_non_block_browser(self, tmp_path):
        """A flow-style or empty browser group gets no nested records — nothing pins into a flow block."""
        nested_prefixes = ("screen", "endpoint", "accept_dialogs", "speed", "timeout")

        flow = tmp_path / "flow.yml"
        flow.write_text(
            "provider: openai\ngeneration_model: g\nclassification_model: c\n"
            "browser: {name: chromium, headless: true}\nstrict: false\ninteractive: false\n",
            encoding="utf-8",
        )
        documented = document_web_config_examples(flow)
        assert not any(record.startswith(nested_prefixes) for record in documented)
        assert "# screen:" not in flow.read_text(encoding="utf-8")

        empty = tmp_path / "empty.yml"
        empty.write_text(
            "provider: openai\ngeneration_model: g\nclassification_model: c\nbrowser: {}\n"
            "strict: false\ninteractive: false\n",
            encoding="utf-8",
        )
        documented = document_web_config_examples(empty)
        assert not any(record.startswith(nested_prefixes) for record in documented)

    def test_document_web_config_examples_marker_matches_the_comment_line_only(self, tmp_path):
        """A sibling's record line is not the key's own marker — ``model`` still gets documented.

        ``model: ''`` is a substring of ``generation_model: ''``; the detection must match the
        emitted comment line so a file carrying the sibling's record (e.g. after a hand edit)
        does not silently skip the key's own.
        """
        web = tmp_path / "web.yml"
        web.write_text(
            "provider: openai\n"
            "# generation_model: ''\n"
            "classification_model: c\n"
            "browser:\n"
            "  name: chromium\n"
            "  headless: true\n"
            "strict: false\n"
            "interactive: false\n",
            encoding="utf-8",
        )

        documented = document_web_config_examples(web)

        assert "base_url: ''" in documented
        assert "model: ''" in documented
        text = web.read_text(encoding="utf-8")
        assert "# model: ''" in text
        # The present sibling record is detected by its own marker — never duplicated.
        assert text.count("generation_model: ''") == 1

    def test_document_web_config_examples_drops_pending_without_browser(self, tmp_path):
        """Without the browser anchor the tail records are dropped silently; the run stays idempotent."""
        web = tmp_path / "web.yml"
        web.write_text(
            "provider: openai\ngeneration_model: g\nclassification_model: c\nstrict: false\ninteractive: false\n",
            encoding="utf-8",
        )

        documented = document_web_config_examples(web)

        assert [record.split("\n", 1)[0] for record in documented] == [
            "base_url: ''",
            "model: ''",
            "generation_prompt: ''",
            "classification_prompt: ''",
        ]
        text = web.read_text(encoding="utf-8")
        assert text.index("# base_url:") < text.index("generation_model:")
        assert text.index("# generation_prompt: ''") < text.index("strict:")
        assert "# polling_timeout" not in text
        assert "# cache_root" not in text
        assert "# browser:" not in text

        snapshot = web.read_bytes()
        assert document_web_config_examples(web) == []
        assert web.read_bytes() == snapshot


class TestRegistrations:
    """Codemanifest usage/annotation registration — never-overwrite and idempotency."""

    @pytest.mark.parametrize("operation", ["usages", "annotations"])
    def test_register_usages_and_annotations_idempotent(self, tmp_path, operation):
        """First run adds/replaces exactly the missing or stale keys; the second is a no-op."""
        config = tmp_path / "config.yml"
        config.write_text(
            "codemanifest:\n"
            "  usages:\n"
            "    pybuggy-api: old.md\n"
            "  annotations: |\n"
            "    Use `pybuggy-api` stale text here\n"
            "    foreign line untouched\n",
            encoding="utf-8",
        )
        yaml = YAML()

        if operation == "usages":
            assert register_usages(config, _USAGE_INPUT) == ["conventions"]
            usages = yaml.load(config)["codemanifest"]["usages"]
            assert usages["pybuggy-api"] == "old.md"
            assert usages["conventions"] == ".goga/usages/conventions.md"
            rerun = lambda: register_usages(config, _USAGE_INPUT)  # noqa: E731
        else:
            assert register_annotations(config, _ANNOTATION_INPUT) == ["pybuggy-api", "conventions"]
            annotations = yaml.load(config)["codemanifest"]["annotations"]
            assert "Use `pybuggy-api` for executing HTTP requests" in annotations
            assert "stale text here" not in annotations
            assert "foreign line untouched" in annotations
            rerun = lambda: register_annotations(config, _ANNOTATION_INPUT)  # noqa: E731

        snapshot = config.read_text(encoding="utf-8")
        assert rerun() == []
        assert config.read_text(encoding="utf-8") == snapshot

    def test_register_annotations_appends_after_plain_scalar_without_trailing_newline(self, tmp_path):
        """A plain-scalar annotations value gains the line on a fresh line, then no-ops."""
        config = tmp_path / "config.yml"
        config.write_text("codemanifest:\n  annotations: some text", encoding="utf-8")

        assert register_annotations(config, {"pybuggy-api": "Use `pybuggy-api` for requests."}) == ["pybuggy-api"]
        assert YAML().load(config)["codemanifest"]["annotations"] == "some text\nUse `pybuggy-api` for requests.\n"
        assert register_annotations(config, {"pybuggy-api": "Use `pybuggy-api` for requests."}) == []

    def test_register_annotations_replaces_only_the_first_matching_line(self, tmp_path):
        """When several lines carry the same backtick reference, exactly the first is replaced."""
        config = tmp_path / "config.yml"
        config.write_text(
            "codemanifest:\n  annotations: |\n    old `pybuggy-api` line\n    another `pybuggy-api` line\n",
            encoding="utf-8",
        )

        assert register_annotations(config, {"pybuggy-api": "Use `pybuggy-api` for requests."}) == ["pybuggy-api"]

        annotations = YAML().load(config)["codemanifest"]["annotations"]
        assert annotations == "Use `pybuggy-api` for requests.\nanother `pybuggy-api` line\n"

    @pytest.mark.parametrize(
        ("operation", "config_text"),
        [
            pytest.param("usages", None, id="usages-absent-file"),
            pytest.param("usages", "", id="usages-empty-file"),
            pytest.param("annotations", None, id="annotations-absent-file"),
            pytest.param("annotations", "", id="annotations-empty-file"),
        ],
    )
    def test_registrations_create_minimal_document_when_no_file(self, tmp_path, operation, config_text):
        """An absent or zero-byte config gets a minimal document carrying the registrations."""
        config = tmp_path / "config.yml"
        if config_text is not None:
            config.write_text(config_text, encoding="utf-8")

        yaml = YAML()

        if operation == "usages":
            assert register_usages(config, _USAGE_INPUT) == ["pybuggy-api", "conventions"]
            assert yaml.load(config)["codemanifest"]["usages"] == _USAGE_INPUT
        else:
            assert register_annotations(config, _ANNOTATION_INPUT) == ["pybuggy-api", "conventions"]

            annotations = yaml.load(config)["codemanifest"]["annotations"]
            assert "Use `pybuggy-api` for executing HTTP requests" in annotations
            assert "`conventions`" in annotations


class TestFixedAssetWriters:
    """Deterministic emission of the packaged conftest template and convention asset."""

    def test_write_pybuggy_conftest_and_test_convention_emit_fixed_assets(self, tmp_path):
        """Both writers emit their fixed sources verbatim and overwrite on every call."""
        conftest = tmp_path / "conftest.py"
        slot = tmp_path / ".goga" / "usages" / "conventions.md"

        write_pybuggy_conftest(conftest)
        write_test_convention(slot)

        assert conftest.read_text(encoding="utf-8") == _EXPECTED_CONFTEST
        packaged = (importlib.resources.files("goga_tool_pybuggy") / "assets" / "conventions.md").read_text(
            encoding="utf-8"
        )
        assert slot.read_text(encoding="utf-8") == packaged
        assert packaged.startswith("# Testing Convention: pytest")

        conftest.write_text("mutated", encoding="utf-8")
        slot.write_text("mutated", encoding="utf-8")

        write_pybuggy_conftest(conftest)
        write_test_convention(slot)

        assert conftest.read_text(encoding="utf-8") == _EXPECTED_CONFTEST
        assert slot.read_text(encoding="utf-8") == packaged


class TestRunBootstrapUsages:
    """The ``run_bootstrap`` packaged-usage distribution — kind-gated roots, split destinations."""

    def test_bootstrap_without_tool_configs_ships_sandbox_only_and_registers_conventions(self, tmp_path, monkeypatch):
        """Without a written tool config no kind ships: only the sandbox quartet lands, only conventions register."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "2.0.3")
        _seed_bootstrap_target(tmp_path)

        assert run_bootstrap(template_mode=True) == 0

        usages = tmp_path / ".goga" / "usages" / "cooks" / "pybuggy"
        assert sorted(path.name for path in usages.iterdir()) == ["sandbox"]
        assert sorted(path.name[:-3] for path in (usages / "sandbox").iterdir()) == sorted(_SANDBOX_STEMS)

        config = YAML().load(tmp_path / ".goga" / "config.yml")
        assert set(config["codemanifest"]["usages"]) == {"conventions"}
        for stem in (*_SANDBOX_STEMS, "api", "asserts", "web"):
            key = "pybuggy-web" if stem == "web" else f"pybuggy-{stem}"
            assert key not in config["codemanifest"]["usages"]
            assert f"`{key}`" not in config["codemanifest"]["annotations"]

    def test_bootstrap_api_kind_copies_api_and_sandbox_and_registers_api_pair(self, tmp_path, monkeypatch):
        """An api-kind tree (api.yml, no web.yml) ships the api pair plus the sandbox quartet — never the web usage.

        Every delivered file lands byte-identical at its destination; only the api pair registers.
        The scope constraint holds: nothing beyond the packaged roots is copied — the plugin and
        commands usage files never reach the target.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "2.0.3")
        _seed_bootstrap_target(tmp_path)
        _seed_api_config(tmp_path)

        assert run_bootstrap(template_mode=False) == 0

        usages = tmp_path / ".goga" / "usages" / "cooks" / "pybuggy"
        assert sorted(path.name for path in usages.iterdir()) == ["api.md", "asserts.md", "sandbox"]

        for stem in ("api", "asserts"):
            assert (usages / f"{stem}.md").read_text(encoding="utf-8") == _PACKAGED_USAGES[stem]

        for stem in _SANDBOX_STEMS:
            assert (usages / "sandbox" / f"{stem}.md").read_text(encoding="utf-8") == _PACKAGED_USAGES[stem]

        config = YAML().load(tmp_path / ".goga" / "config.yml")
        registered = config["codemanifest"]["usages"]
        annotations = config["codemanifest"]["annotations"]

        for stem in ("api", "asserts"):
            assert registered[f"pybuggy-{stem}"] == f".goga/usages/cooks/pybuggy/{stem}.md"
            assert f"`pybuggy-{stem}`" in annotations

        for stem in _SANDBOX_STEMS:
            assert f"pybuggy-{stem}" not in registered
            assert f"`pybuggy-{stem}`" not in annotations

        # The web usage never crosses into an api-only project — neither file nor registration.
        assert "pybuggy-web" not in registered
        assert "`pybuggy-web`" not in annotations

    def test_bootstrap_web_kind_copies_web_and_sandbox_and_registers_web_usage(self, tmp_path, monkeypatch):
        """A web-kind tree (web.yml, no api.yml) ships the web usage plus the sandbox quartet — never the api files."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "2.0.3")
        _seed_bootstrap_target(tmp_path)
        _seed_web_config(tmp_path)

        assert run_bootstrap(template_mode=False) == 0

        usages = tmp_path / ".goga" / "usages" / "cooks" / "pybuggy"
        assert sorted(path.name for path in usages.iterdir()) == ["pybuggy-web.md", "sandbox"]
        assert (usages / "pybuggy-web.md").read_text(encoding="utf-8") == _PACKAGED_USAGES["pybuggy-web"]

        config = YAML().load(tmp_path / ".goga" / "config.yml")
        registered = config["codemanifest"]["usages"]
        # The api usage keys never cross into a web-only project; the web usage key is its own
        # stem — no ``pybuggy-`` prefixing at the registration step.
        assert set(registered) == {"pybuggy-web", "conventions"}
        assert "`pybuggy-web`" in config["codemanifest"]["annotations"]
        assert "`pybuggy-api`" not in config["codemanifest"]["annotations"]

    def test_bootstrap_template_mode_skips_existing_targets(self, tmp_path, monkeypatch, caplog):
        """Template mode keeps an existing sandbox-usage sentinel across reruns; bare mode overwrites it."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "2.0.3")
        _seed_bootstrap_target(tmp_path)
        target = tmp_path / ".goga" / "usages" / "cooks" / "pybuggy" / "sandbox" / "sandbox-session.md"
        target.parent.mkdir(parents=True)
        target.write_text("sentinel\n", encoding="utf-8")

        with caplog.at_level(logging.INFO):
            assert run_bootstrap(template_mode=True) == 0

        assert target.read_text(encoding="utf-8") == "sentinel\n"

        with caplog.at_level(logging.INFO):
            assert run_bootstrap(template_mode=True) == 0

        assert target.read_text(encoding="utf-8") == "sentinel\n"
        assert any(
            record.message == "existing file kept untouched" and record.path == str(target) for record in caplog.records
        )

        monkeypatch.setattr(click, "confirm", lambda *_args, **_kwargs: False)
        assert run_bootstrap(template_mode=False) == 0
        assert target.read_text(encoding="utf-8") == _PACKAGED_USAGES["sandbox-session"]

    def test_bootstrap_keeps_a_stale_flat_sandbox_copy(self, tmp_path, monkeypatch):
        """A flat sandbox copy from an earlier distribution survives — no migration of old layouts."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(importlib.metadata, "version", lambda _name: "2.0.3")
        _seed_bootstrap_target(tmp_path)
        stale = tmp_path / ".goga" / "usages" / "cooks" / "pybuggy" / "sandbox-session.md"
        stale.parent.mkdir(parents=True)
        stale.write_text("old flat copy\n", encoding="utf-8")

        assert run_bootstrap(template_mode=True) == 0

        assert stale.read_text(encoding="utf-8") == "old flat copy\n"
        fresh = stale.parent / "sandbox" / "sandbox-session.md"
        assert fresh.read_text(encoding="utf-8") == _PACKAGED_USAGES["sandbox-session"]
