"""Commands/init cell facade — the 23 init-cell routines across init, session, and bootstrap."""

from .bootstrap import (
    document_config_examples,
    ensure_review_skip,
    install_pybuggy,
    register_annotations,
    register_usages,
    write_pybuggy_conftest,
    write_test_convention,
)
from .init import init_cmd, resolve_init_mode, run_bootstrap, run_init
from .session import (
    amend_pybuggy_config,
    build_config_amendments,
    build_config_data,
    build_web_config_data,
    declare_pybuggy_session,
    parse_specs,
    pybuggy_questions,
    run_session,
    survey_api_options,
    survey_autonomy,
    survey_specs,
    survey_web_config,
)

__all__ = [
    "amend_pybuggy_config",
    "build_config_amendments",
    "build_config_data",
    "build_web_config_data",
    "declare_pybuggy_session",
    "document_config_examples",
    "ensure_review_skip",
    "init_cmd",
    "install_pybuggy",
    "parse_specs",
    "pybuggy_questions",
    "register_annotations",
    "register_usages",
    "resolve_init_mode",
    "run_bootstrap",
    "run_init",
    "run_session",
    "survey_api_options",
    "survey_autonomy",
    "survey_specs",
    "survey_web_config",
    "write_pybuggy_conftest",
    "write_test_convention",
]
