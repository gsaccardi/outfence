# Outfence brand guide

**Working identity · v0.1 · 12 September 2026**

![Outfence identity proposal](assets/brand-board.png)

## Name and positioning

**Outfence** combines outbound activity with a boundary. Pronounce it “OUT-fens.” Use Outfence in prose and `outfence` for the proposed repository/CLI. The lowercase wordmark is intentional.

Primary line: **Know where your agents connect.**

Supporting line: **Local policies. Reviewable evidence.**

One sentence: “Outfence helps developers inspect and control outbound connections from containerized AI agent runs.” Until implemented, qualify this as the proposed product.

Alternative considered: Egresslane, technically clear but longer and less conversational. Tracegate was rejected because relevant software products already use it. Name clearance and handles remain pending; see [research notes](../docs/RESEARCH.md).

## Symbol

An open rectangular boundary frames a dot and an outbound arrow. The mark also suggests an E for egress. It is original vector geometry with no external illustrations or icon dependencies. Use it to represent visible, intentional connections. It is not a certification mark.

Minimum display size: 24 px symbol, 160 px complete wordmark. Keep clear space around the visible symbol equal to at least 15% of its width. Keep proportions intact. Use the monochrome mark on busy backgrounds. Do not add shields, gradients, glows, rotations, or extra outlines.

## Palette

| Token | Hex | Use |
|---|---|---|
| Ink | `#102B2A` | Primary text and dark backgrounds |
| Mint | `#A6F0CD` | Brand accent on ink; button background with ink text |
| Paper | `#F7F5EF` | Light canvas and text on ink |
| Slate | `#526563` | Secondary text on paper |
| Line | `#D6DDD5` | Dividers and decorative boundaries |
| Success | `#17664D` | Allowed/passed label on paper |
| Warning | `#865500` | Observation or incomplete coverage label on paper |
| Danger | `#A43135` | Blocked/error label on paper |

Use ink text on mint. Mint is unsuitable for small text on paper. Pair every state color with a word or symbol; never communicate policy decisions through color alone. Divider color is decorative and must not be the only indicator of an interactive control.

## Typography and layout

Current artwork: Arial Bold for headings/wordmark, Arial for body, Courier New for small technical labels. These are system-font choices; no font files are distributed. SVG wordmarks retain editable text and may differ on systems without the font. Use PNGs for consistent GitHub display or outline the text before preparing professional print assets.

Web fallback stacks: `Arial, Helvetica, sans-serif` and `'Courier New', monospace`. Use a 4 px spacing base, generous margins, short headings, and clear labels. Prefer rounded panels with restrained radii to ornamental graphics.

## Voice

Precise, calm, useful. Name the observed action and its scope.

Use: “Blocked telemetry.example:443 because it is outside your allowlist.”

Use: “Coverage incomplete: the collector stopped before the workload exited.”

Avoid: “Leak-proof,” “sovereignty certified,” “complete visibility,” or “production-ready” without supporting evidence. Do not substitute investor language for a concrete developer job.

## Assets

| Asset | Vector | Raster | Intended use |
|---|---|---|---|
| Ink mark | [SVG](assets/mark-ink.svg) | [PNG](assets/mark-ink.png) | Transparent icon on light backgrounds |
| White mark | [SVG](assets/mark-white.svg) | [PNG](assets/mark-white.png) | Transparent icon on dark backgrounds |
| Avatar | [SVG](assets/avatar.svg) | [PNG](assets/avatar.png) | 512 × 512 GitHub avatar |
| Light wordmark | [SVG](assets/wordmark-light.svg) | [PNG](assets/wordmark-light.png) | 760 × 180 transparent lockup |
| Dark wordmark | [SVG](assets/wordmark-dark.svg) | [PNG](assets/wordmark-dark.png) | 760 × 180 dark lockup |
| README banner | [SVG](assets/banner.svg) | [PNG](assets/banner.png) | 1600 × 560 banner |
| Social preview | [SVG](assets/social-preview.svg) | [PNG](assets/social-preview.png) | 1280 × 640 social card |
| Brand board | [SVG](assets/brand-board.svg) | [PNG](assets/brand-board.png) | 1600 × 1200 identity overview |

Machine-readable colors and typography: [tokens.json](tokens.json). Rebuild artwork with `python3 scripts/build_brand.py` from the repository root. Requires Pillow and the documented system fonts, or `OUTFENCE_FONT_DIR` pointing to equivalent font filenames.

The repository and artwork use Apache-2.0; the brand name remains provisional. No trademark, domain, package, or GitHub organization has been registered by this work.
