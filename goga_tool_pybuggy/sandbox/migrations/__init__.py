"""`goga_tool_pybuggy.sandbox.migrations` cell facade — the sandbox DB migration set.

The facade carries the eight contract names of the cell: ``MigrationError`` and
``MigrationFile`` (the failure family and the parsed unit), ``parse_migration_file`` and
``load_migration_set`` (the goose-SQL parsing plane), ``check_local_migrations`` and
``check_git_url`` (the load-time source shape checks), and ``apply_migrations`` and
``run_migrations`` (the execution plane and the source-resolution orchestration).
"""

from .apply import apply_migrations, run_migrations
from .errors import MigrationError
from .goose import MigrationFile, load_migration_set, parse_migration_file
from .source import check_git_url, check_local_migrations

__all__ = [
    "MigrationError",
    "MigrationFile",
    "apply_migrations",
    "check_git_url",
    "check_local_migrations",
    "load_migration_set",
    "parse_migration_file",
    "run_migrations",
]
