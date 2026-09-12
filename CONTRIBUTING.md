# Contributing to Outfence

Start with a small, reproducible problem. The current alpha is a proxy/report tool; container isolation is a separate investigation. Read the [README](README.md) and [security scope](SECURITY.md) before proposing stronger security claims.

## Development

Python 3.10+ on macOS/Linux:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
python -m pip install --no-build-isolation -e .
ruff check outfence tests
ruff format --check outfence tests
python -m unittest discover -s tests -v
python -m build --no-isolation
```

Use `ruff format outfence tests` to format changes. To check packaging, install the built wheel into a fresh virtual environment and run `scripts/smoke_install.py` with that environment's Python. It exercises the installed command from outside the checkout.

Tests must not require paid APIs or external services. Use local fixtures, explicit synthetic endpoint mappings, and destination-side assertions. Do not expand the public policy schema to allow the internal fixture bypass.

## Pull requests

Explain the user-visible problem, the change, and how you verified it. Add regression coverage for behavior changes. Keep error and report strings free of request bodies, credentials, raw paths, and environment values. Update documentation when the supported behavior changes.

Report normal bugs with the issue template. Follow [SECURITY.md](SECURITY.md) for sensitive findings. Treat contributors respectfully, focus criticism on the work, and do not post personal or confidential information.

By submitting a contribution, you agree that it is provided under this repository's Apache-2.0 license. No additional CLA is required. Source files, tests, documentation, and generated artwork are included under that license; bundled third-party fonts are not distributed.
