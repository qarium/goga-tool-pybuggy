"""pull command handler - clone specs from git repositories."""

import logging
import shutil
import tempfile
import urllib.parse
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

import click
from git import GitCommandError, Repo

from ...config import load_config

logger = logging.getLogger(__name__)


def _validate_no_path_traversal(path_str: str, path_type: str) -> None:
    """Validate that a path string doesn't contain path traversal patterns.

    Args:
        path_str: The path string to validate
        path_type: Description of the path (for error messages)

    Raises:
        click.ClickException: If path contains traversal patterns
    """
    if ".." in path_str or path_str.startswith("/"):
        raise click.ClickException(f"invalid {path_type} (must be relative path without '..'): {path_str}")


def _validate_git_url(url: str) -> None:
    """Validate that a git URL is safe to clone.

    Args:
        url: The git URL to validate

    Raises:
        click.ClickException: If URL is disallowed
    """
    parsed = urllib.parse.urlparse(url)
    # Only allow specific schemes
    allowed_schemes = {"https", "http", "git", "ssh", "git@github.com"}
    if parsed.scheme and parsed.scheme not in allowed_schemes:
        raise click.ClickException(
            f"disallowed git URL scheme: {parsed.scheme} (allowed: {', '.join(sorted(allowed_schemes))})"
        )
    # Reject URLs with embedded credentials
    if "@" in parsed.netloc and parsed.scheme not in ("ssh", ""):
        raise click.ClickException(f"git URL must not contain embedded credentials: {url}")


@contextmanager
def clone_repo(url: str, ref: Optional[str] = None):
    """Context manager for shallow git clone with automatic cleanup.

    Yields the temporary directory path containing the cloned repository.

    Args:
        url: Clone URL consumed by shallow-clone.
        ref: Optional git ref (branch or tag name) to clone; when None the
            remote default branch is cloned via ``depth=1``.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        logger.debug(f"Cloning {url} to {tmp_dir}")
        # branch=None makes GitPython omit --branch, preserving the default-branch behavior.
        Repo.clone_from(url, tmp_dir, depth=1, branch=ref)
        yield tmp_dir


def _validate_and_prepare_destination(entry) -> tuple:
    """Validate git URL and prepare destination path with security checks.

    Returns:
        Tuple of (url, destination) after validation
    """
    _validate_no_path_traversal(entry.git.location, "git.location")
    _validate_no_path_traversal(entry.location, "location")
    _validate_git_url(entry.git.url)

    destination = Path.cwd() / entry.location
    resolved_dest = destination.resolve()
    cwd_resolved = Path.cwd().resolve()
    if not str(resolved_dest).startswith(str(cwd_resolved)):
        raise click.ClickException(f"destination path escapes working directory: {entry.location}")
    return entry.git.url, destination


def _resolve_refs(ref: Optional[str | tuple]) -> tuple:
    """Normalize a ref override into a global ref and a per-spec ref map.

    Args:
        ref: None (no override), a global ref string, or a tuple of items where
            each item is a global ref string or a ``(spec_name, ref)`` pair
            (per-spec override produced by ``SmartParam``).

    Returns:
        A ``(global_ref, per_spec)`` tuple: ``global_ref`` is the global override
        or None; ``per_spec`` maps spec names to their per-spec ref.
    """
    if ref is None or isinstance(ref, str):
        return ref, {}

    global_ref = None
    per_spec: dict = {}
    for item in ref:
        if item is None:
            continue

        if isinstance(item, tuple):
            spec_name, spec_ref = item
            per_spec[spec_name] = spec_ref
        else:
            global_ref = item

    return global_ref, per_spec


def _effective_ref(
    name: str, git_ref: Optional[str], global_ref: Optional[str], per_spec: dict
) -> Optional[str]:
    """Resolve the effective ref for a single spec.

    Per-spec override wins, then the global override, then the config ``git.ref``.

    Args:
        name: Spec name to resolve the ref for.
        git_ref: The config ``git.ref`` for the spec (may be None).
        global_ref: The global override ref (may be None).
        per_spec: Per-spec override map.

    Returns:
        The effective ref, or None to clone the remote default branch.
    """
    if name in per_spec:
        return per_spec[name]

    if global_ref is not None:
        return global_ref

    return git_ref


def _validate_per_spec_refs(per_spec: dict, config_specs: dict) -> None:
    """Raise ClickException if a per-spec ref names a spec absent from the configuration.

    Args:
        per_spec: Per-spec override map (spec name -> ref).
        config_specs: The configuration's specs (the set of valid spec names).

    Raises:
        click.ClickException: If any per-spec ref names a spec not in the configuration.
    """
    unknown = [name for name in per_spec if name not in config_specs]

    if unknown:
        raise click.ClickException(f"unknown spec in --ref: {', '.join(sorted(unknown))}")


def run_pull(spec_name: Optional[str], ref: Optional[str | tuple] = None) -> None:
    """Clone specs from git repositories to local locations.

    Loads config from the fixed config path and copies spec files from remote
    git repositories to local paths. Idempotent - repeated runs overwrite files.

    Args:
        spec_name: Optional spec name to pull; if None, pulls all specs
        ref: Optional git ref override. Accepts: None (no override); a global ref
            string applied to every selected spec; or a tuple of items where each
            item is a global ref string or a ``(spec_name, ref)`` pair overriding
            a single spec (per-spec wins over global). When no override applies,
            the config ``git.ref`` is used (None there falls back to the remote
            default branch).

    Raises:
        click.ClickException: If spec_name not found, a per-spec ref names an unknown
            spec, or clone/copy fails
    """
    # Load config from the fixed path
    config = load_config()

    # Select specs
    if spec_name is not None:
        if spec_name not in config.specs:
            raise click.ClickException(f"spec not found: {spec_name}")
        specs = {spec_name: config.specs[spec_name]}
    else:
        specs = config.specs

    # Normalize the ref override: a global ref plus an optional per-spec map.
    global_ref, per_spec = _resolve_refs(ref)

    # A per-spec ref must name a spec that exists in the configuration.
    _validate_per_spec_refs(per_spec, config.specs)

    # Process each spec
    for name, entry in specs.items():
        if entry.git is None:
            logger.warning(f"no remote source; treated as local: {name}")
            continue

        # Validate paths and prepare destination
        git_url, destination = _validate_and_prepare_destination(entry)

        # Effective ref: per-spec override wins, then global, then config git.ref;
        # None there means clone the remote default branch.
        effective_ref = _effective_ref(name, entry.git.ref, global_ref, per_spec)

        try:
            with clone_repo(git_url, effective_ref) as repo_root:
                source = Path(repo_root) / entry.git.location
                if not source.exists():
                    raise click.ClickException(f"spec path not found in repo: {entry.git.location}")

                destination.parent.mkdir(parents=True, exist_ok=True)

                if source.is_dir():
                    shutil.copytree(source, destination, dirs_exist_ok=True)
                else:
                    shutil.copy2(source, destination)

                logger.info(f"Pulled {name} to {destination}")

        except GitCommandError as exc:
            raise click.ClickException(f"git clone failed: {exc}") from exc
        except OSError as exc:
            raise click.ClickException(f"file operation failed: {exc}") from exc


class SmartParam(click.ParamType):
    """Parses a ``--ref`` value into a global ref or a per-spec ``(name, ref)`` pair.

    A value without ``:`` is a global ref (applies to every selected spec); a
    value of the form ``NAME:REF`` overrides the ref for a single spec.
    """

    name = "smart-ref"

    def convert(self, value, _param, _ctx):
        """Parse one --ref value into None, a global ref, or a per-spec (name, ref) pair.

        None/'' -> None (no override); a value without ':' -> the value (global ref);
        'NAME:REF' -> the (name, ref) pair, splitting on the first ':' only.
        """
        if value is None or value == "":
            return None

        if ":" not in value:
            return value

        key, val = value.split(":", 1)

        return key, val


@click.command("pull")
@click.option("--spec", "spec_name", default=None, help="Spec name to pull")
@click.option(
    "--ref",
    "ref",
    type=SmartParam(),
    multiple=True,
    default=(),
    help="Git ref (branch/tag); 'NAME:REF' overrides the ref for a single spec",
)
def pull_cmd(spec_name: Optional[str], ref: tuple = ()) -> None:
    """Clone specs from git repositories."""
    run_pull(spec_name, ref)
