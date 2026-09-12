> Historical discovery copy. The current runnable alpha has [updated release materials](RELEASE.md).

# GitHub launch materials

Draft copy. Publication is a later action; nothing has been uploaded or reserved.

## Repository metadata

Name: `outfence` (proposed). Description: “Inspect and control outbound connections from containerized AI agent runs. Local policies. Reviewable evidence.”

Topics: `ai-agents`, `agent-security`, `network-policy`, `egress`, `developer-tools`, `self-hosted`, `open-source`.

Avatar: `brand/assets/avatar.png` (512 × 512). Social preview: `brand/assets/social-preview.png` (1280 × 640). README banner: `brand/assets/banner.png` (1600 × 560). Editable vector versions are alongside the PNGs.

## Discovery announcement

We're exploring Outfence: an open source tool to help developers understand and control where containerized AI agents connect.

The first proposal is deliberately small: run a workflow, inspect its outbound destinations, enforce a reviewed allowlist, and export local evidence. The PRD and visual identity are public for feedback; the CLI is not implemented yet.

If you've had to explain an agent's network behavior to a customer security team, we'd like to learn how you handled it. Sanitized examples and criticism of the scope are especially useful.

## Future alpha announcement template

Use only after implementation and acceptance evidence exists. Replace every bracketed item before publishing:

“Outfence [version] is available for [verified environment]. Run a containerized agent, inspect outbound HTTP(S) destinations, and enforce a local allowlist. Get started: [verified quickstart]. Coverage and limitations: [verified documentation].”

## Publication checklist

- [ ] PM reviews PRD decisions D1–D8.
- [ ] Check and reserve desired repository, organization, package, and domain names.
- [ ] Confirm name and asset rights before commercial branding.
- [ ] Approve and add license text; proposed code license is Apache-2.0.
- [ ] Configure a working private vulnerability-reporting channel before shipping executable security tooling.
- [ ] Confirm public README accurately distinguishes proposals from implemented behavior.
- [ ] Upload the avatar and social preview, set description and topics.
- [ ] Keep examples synthetic; review all files for private information.
- [ ] Publish only with explicit authorization for the destination repository.

## First backlog items

1. Validate three concrete enterprise evidence requests.
2. Compare the same fixtures and reports with GitHub AWF.
3. Write the supported-runtime/backend decision after a feasibility spike.
4. Freeze policy and event schema with acceptance fixtures.
5. Implement the P0 CLI and offline report only after scope validation.
