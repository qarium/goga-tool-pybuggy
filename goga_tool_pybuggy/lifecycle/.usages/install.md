# pybuggy — post-install provisioning via the lifecycle install hook

## Domain

The platform-facing post-install setup of the web exploration agent CLI. The audience is
the goga platform, not user code: `goga install` (single `goga install pybuggy`, bulk over
the project tools, and `goga install --local <path>:pybuggy`) imports the package facade
after a successful pip and calls its `install` slot, which this cell owns.

## Entry point

The hook is not called by users or test suites — the platform calls it:

    # inside goga install, after pip
    from goga_tool_pybuggy import install

    install(user=<initiating user>)  # SUDO_USER under sudo, else the current OS user

A manual call is legal as a recovery step after a fixed environment:

    from goga_tool_pybuggy import install

    install()

## Behavior

- npm on PATH → `npm install -g @playwright/cli`, then `playwright-cli install --skills --global`.
- npm absent → one warning, a quiet skip, and the install still succeeds (api/sandbox-only
  environments without node are supported).
- A present-but-failing command raises RuntimeError carrying the command's stderr; the
  platform turns it into a failed install (exit 1).
- When the process runs as root with an initiating user (SUDO_USER), the skills step runs
  as `sudo -H -u <user>` so the global skills land in the initiating user's HOME; the npm
  step always runs as the current process user.
- Browser binaries are NOT installed here — `playwright install --with-deps <browser>`
  stays a Dockerfile concern (per-project browser from the web config).

## Preconditions and side effects

- node/npm on PATH and network access to the npm registry are required for the web kind;
  environments without npm install cleanly with a warning.
- Writes into the npm global tree and the user's home (skills); needs npm-global write
  rights for the running user.
- Re-runs on every `goga install` — no skip-if-present and no version pinning; npm
  resolves the package each time.
