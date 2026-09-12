# Release candidate: Outfence 0.1.0a1

## Suggested GitHub release title

Outfence 0.1.0a1 — local connection-policy alpha

## Release description

Outfence's first alpha lets developers inspect proxy-routed outbound connections, compare enforce and observe modes, and save offline HTML/JSON reports. It includes a no-credentials localhost demo and an installable Python CLI with `init`, `check`, `demo`, and `run`.

Requires Python 3.10+ on macOS/Linux. No third-party runtime dependencies. Licensed Apache-2.0.

This release is a local development proxy, not a network sandbox. Direct connections can bypass it. See SECURITY.md and the README for coverage, protocol restrictions, and resource limits.

## Build artifacts

```sh
python -m build --no-isolation
```

Expected files: `dist/outfence-0.1.0a1-py3-none-any.whl` and `dist/outfence-0.1.0a1.tar.gz`.

Install a wheel with `python -m pip install PATH_TO_WHEEL`. Smoke-test the installed package from outside the checkout with `python scripts/smoke_install.py`. No PyPI release or available registry name is claimed.

## Maintainer publication steps

- [x] GitHub repository: [gsaccardi/outfence](https://github.com/gsaccardi/outfence).
- [x] Create the public repository. The reviewed alpha source is prepared for the initial push to main.
- [x] Enable GitHub private vulnerability reporting.
- [ ] Confirm CI passes on all four configured Python/OS combinations.
- [ ] Review source, assets, license, and package contents; exclude local run evidence and environment files.
- [ ] Tag the approved source `v0.1.0a1` and create the release using the description above.
- [ ] Attach artifacts built from that tag; do not reuse builds from a different working tree.
- [ ] Set the repository avatar/social preview and description from the brand kit.

Repository description: “A local proxy CLI for inspecting agent connections, applying destination policies, and exporting offline reports.”

Suggested topics: ai-agents, proxy, developer-tools, network-policy, python, self-hosted.

The public GitHub repository is created. Tagged releases and package-registry publication remain separate from the initial source push.

## Local verification for this candidate

On macOS / Python 3.13: 20 unit/integration tests passed, Ruff lint and format checks passed, wheel and source archive built, and the installed-package smoke test passed outside the checkout (init/check, enforce, observe, edited allow-all policy). Package inspection verified Apache-2.0 metadata, zero runtime dependencies, and exclusion of local reports/environment files. The hosted Linux/macOS CI matrix has not run yet.

## Follow-up validation

The macOS installed-demo timeout was traced to unnecessary reverse DNS during local HTTP-server binding. Loopback servers now skip that lookup, with a regression test guarding it. The [four-job CI run for the fix](https://github.com/gsaccardi/outfence/actions/runs/34688309142) passed on Linux/macOS and Python 3.10/3.13. The real Ollama agent walkthrough documents separate manual model/tool verification.
