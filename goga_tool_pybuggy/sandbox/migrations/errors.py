"""MigrationError entity: the failure family of the migrations domain."""


class MigrationError(RuntimeError):
    """A failed migration operation.

    Every failure in the migrations domain surfaces as this type: source resolution, naming,
    parsing, and execution. The message names the migration file or the source step and the
    underlying cause. Exposed through the cell facade — the engines catch it by name to map
    into their own error family.
    """
