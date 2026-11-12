# Local setup and release packaging

Python 3.11+ is required. The release was validated using CPython 3.13 on macOS
arm64. C parsing uses packaged tree-sitter wheels; no compiler, C SDK or enterprise
service is needed when compatible binary dependencies are available.

## Development install

From the checkout (or extracted source archive):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
.venv/bin/python -m pip check
.venv/bin/fcgc doctor --config config/local.toml
.venv/bin/fcgc info
```

`requirements.lock` pins the tested development and build tools as well as runtime
dependencies. `requirements-runtime.lock` pins runtime dependencies only.
`pyproject.toml` keeps compatible ranges for normal package installation. Pins do
not guarantee identical wheels across Python/platform targets. Do not assume the
provided macOS wheelhouse works on Linux or Windows.

## Prepare an offline transfer

On a machine with the same Python/platform target and approved package-index access:

```sh
.venv/bin/python -m pip download -r requirements.lock -d wheelhouse
.venv/bin/python scripts/build_release.py --output outputs/packages/transfer-0.13.0
shasum -a 256 wheelhouse/*.whl > wheelhouse/SHA256SUMS
# The builder writes outputs/packages/transfer-0.13.0/SHA256SUMS.
```

The output directory must be fresh. This helper builds the wheel from a fresh
source-archive extraction, so stale checkout `build/lib` files cannot leak into
the wheel. Direct builds from a reused build tree can retain removed resources.
Inspect both archives before approval. Keep private settings in files ending in
`.private.toml`, `.private.json`, `.local.toml` or `.local.json`; those names and
`.env` files are ignored and excluded from packaging. Ordinary example configs
are packaged deliberately and must contain no secrets.

Transfer the source archive, release wheel, lock files and target wheelhouse using
an approved channel. Verify checksums, then install and build without an index:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install --no-index --find-links wheelhouse -r requirements.lock
.venv/bin/python -m pip install --no-index --no-deps --no-build-isolation -e .
.venv/bin/python scripts/build_release.py --output outputs/packages/transfer-0.13.0
```

For a runtime-only wheel install into a fresh environment:

```sh
python3 -m venv /tmp/fcgc-runtime
/tmp/fcgc-runtime/bin/python -m pip install --no-index --find-links wheelhouse -r requirements-runtime.lock
/tmp/fcgc-runtime/bin/python -m pip install --no-index --no-deps outputs/packages/transfer-0.13.0/fcgc-0.13.0-py3-none-any.whl
/tmp/fcgc-runtime/bin/fcgc doctor
```

The wheel includes fixtures, configs and canonical checker instructions. The source
archive additionally includes benchmark annotations, tests and docs. Full benchmark
experiments need `--dataset-root` pointing to the checkout/source archive's
`benchmarks/v2`; preserve its relative fixture layout. An installed wheel alone
supports artifact checking, fixture retrieval, segmentation and frozen-task checks.

## Configuration and environment

No environment variables are required. CLI provider commands accept `--config` or
the optional `FCGC_CONFIG` environment variable; explicit CLI paths take precedence.
Relative config paths are relative to the working directory. Replay paths inside
provider TOMLs are relative to that TOML. Experiment/evaluation paths are relative
to their TOML. `FCGC_CONFIG` does not override an experiment's locked provider tables.
Copying `.env.example` does not load it; use an explicit shell export if desired.
No credential variables, WD URLs or guessed MCP tool names are implemented.

Ollama requires explicit TOML `model`, `allow_network=true` even on loopback,
and a pre-provisioned local model. Non-loopback or remote-backed models also require
`allow_remote=true`. The adapter never installs a model. See [checker operation](checking.md).

## Release procedure

Run pytest, Ruff lint/format, `compileall`, `pip check`, dataset quality validation,
the offline secret-pattern scan and the one-command acceptance workflow. Rebuild
the wheel/source archive, install into a fresh environment without an index and
run diagnostics and acceptance there. Save logs, checksums, evaluation reports and
known limitations with the release. Use a fresh experiment output after any source,
prompt, corpus or configuration change. No static type checker is configured;
compilation and contract tests are not a substitute for one.

A container is optional and is not supplied as a verified deployment target. WD
must select an approved base image, Linux wheels and volume/security policy before
container packaging can be validated. Local builds never contact WD systems.
