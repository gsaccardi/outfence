"""Record a styled Outfence terminal run as an SVG, animated by default. Standard library only.

    python3 scripts/terminal_svg.py docs/assets/terminal-demo.svg
    python3 scripts/terminal_svg.py out.svg --static --from "Connecting" -- ./my_demo.sh

The command (default: the offline demo) runs in a temporary directory with styling forced
on, so its report paths are replaced with ~/project before rendering. Half-block cells are
drawn as rectangles, so the goose stays crisp whatever font the viewer has.
"""

import argparse
import html
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

INK, PAPER, MIST, ACID = "#171917", "#FAFAF7", "#C2C6BC", "#D9F378"
CELL, LINE, PAD, BAR = 8.4, 18, 16, 34
TOKEN = re.compile(r"\x1b\[([0-9;]*)m|([^\x1b]+)")
FONT = "'IBM Plex Mono', 'SFMono-Regular', Menlo, Consolas, 'Liberation Mono', monospace"


def capture(command, columns):
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(
            os.environ, OUTFENCE_COLOR="always", COLORTERM="truecolor", OUTFENCE_THEME="dark"
        )
        env.update(COLUMNS=str(columns), PYTHONPATH=str(Path(__file__).resolve().parents[1]))
        result = subprocess.run(command, cwd=tmp, env=env, capture_output=True, text=True)
        text = result.stdout.replace(str(Path(tmp).resolve()), "~/project")
    # Never publish the recorder's own paths: temporary directories and the home directory.
    return text.replace(tmp, "~/project").replace(str(Path.home()), "~")


def cells(line):
    """Turn one line of SGR-colored text into (char, fg, bg, bold) cells."""
    fg = bg = None
    bold, out = False, []
    for codes, text in TOKEN.findall(line):
        if text:
            out += [(char, fg, bg, bold) for char in text]
            continue
        parts = [int(p) for p in codes.split(";") if p] or [0]
        while parts:
            code = parts.pop(0)
            if code == 0:
                fg = bg = None
                bold = False
            elif code == 1:
                bold = True
            elif code in (38, 48) and parts[:1] == [2]:
                color = "#%02X%02X%02X" % tuple(parts[1:4])
                parts = parts[4:]
                fg, bg = (color, bg) if code == 38 else (fg, color)
    return out


def draw(row, y):
    """SVG for one terminal line: background and pixel rectangles first, then text runs."""
    rects, texts = [], []
    for x, (char, fg, bg, bold) in enumerate(row):
        top = bottom = None
        if char == "▀":
            top, bottom = fg, bg
        elif char == "▄":
            top, bottom = bg, fg
        elif bg:
            rects.append((x, 0, 2, bg))
        if top:
            rects.append((x, 0, 1, top))
        if bottom:
            rects.append((x, 1, 1, bottom))
        if char not in "▀▄ " or (char == " " and texts and texts[-1][0] + len(texts[-1][1]) == x):
            if texts and texts[-1][0] + len(texts[-1][1]) == x and texts[-1][2:] == (fg, bold):
                texts[-1][1] += char
            elif char != " ":
                texts.append([x, char, fg, bold])
    merged = []
    for x, half, height, color in sorted(rects, key=lambda r: (r[1], r[0])):
        last = merged[-1] if merged else None
        if last and last[1:] == [half, height, color] and last[0] + last[4] == x:
            last[4] += 1
        else:
            merged.append([x, half, height, color, 1])
    svg = [
        f'<rect x="{PAD + x * CELL:.1f}" y="{y + half * LINE / 2:.1f}" width="{w * CELL + 0.3:.1f}"'
        f' height="{height * LINE / 2 + 0.3:.1f}" fill="{color}"/>'
        for x, half, height, color, w in merged
    ]
    for x, text, fg, bold in texts:
        text = text.rstrip()
        weight = ' font-weight="700"' if bold else ""
        svg.append(
            f'<text x="{PAD + x * CELL:.1f}" y="{y + LINE * 0.75:.1f}" fill="{fg or PAPER}"{weight}'
            f' textLength="{len(text) * CELL:.1f}" lengthAdjust="spacing">{html.escape(text)}</text>'
        )
    return "".join(svg)


def render(text, title, prompt, animate, start):
    lines = text.rstrip("\n").split("\n")
    if start:
        first = next((i for i, line in enumerate(lines) if start in line), 0)
        lines = lines[first:]
    rows = [cells(f"\x1b[38;2;217;243;120m$\x1b[0m {prompt}")] + [cells(line) for line in lines]
    width = max(len(row) for row in rows)
    w, h = PAD * 2 + width * CELL, BAR + PAD + len(rows) * LINE + PAD
    # Reveal: the prompt, then the banner at once, then one line at a time; the report cascades.
    times, clock = [], 0.4
    for index, row in enumerate(rows):
        pixel = any(c[0] in "▀▄" for c in row)
        step = 0.0 if index == 0 else 0.6 if index == 1 else 0.03 if pixel or not row else 0.22
        clock += step
        times.append(round(clock, 2))
    total = clock + 7
    style, body = [], []
    for index, row in enumerate(rows):
        y = BAR + PAD + index * LINE
        if animate:
            name = f"k{index}"
            show = times[index] / total * 100
            style.append(
                f"@keyframes {name}{{0%,{show:.2f}%{{opacity:0}}{show + 0.01:.2f}%,100%{{opacity:1}}}}"
                f".{name}{{opacity:0;animation:{name} {total:.1f}s linear infinite}}"
            )
            body.append(f'<g class="{name}">{draw(row, y)}</g>')
        else:
            body.append(draw(row, y))
    dots = "".join(
        f'<circle cx="{PAD + 6 + i * 18}" cy="{BAR / 2}" r="5.5" fill="{color}"/>'
        for i, color in enumerate(("#3A3D39", "#3A3D39", ACID))
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}"'
        f' role="img" aria-label="{html.escape(title)}">'
        f"<title>{html.escape(title)}</title>"
        f"<style>text{{font-family:{FONT};font-size:14px;white-space:pre}}{''.join(style)}</style>"
        f'<rect width="{w:.0f}" height="{h:.0f}" rx="10" fill="{INK}"/>'
        f'<rect x="0.5" y="0.5" width="{w - 1:.0f}" height="{h - 1:.0f}" rx="10" fill="none" stroke="#2C2F2B"/>'
        f"{dots}"
        f'<text x="{w / 2:.0f}" y="{BAR / 2 + 5}" fill="{MIST}" text-anchor="middle">{html.escape(title)}</text>'
        f"{''.join(body)}</svg>\n"
    )


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("output")
    parser.add_argument("--columns", type=int, default=100)
    parser.add_argument("--title", default="outfence demo")
    parser.add_argument("--prompt", default="outfence demo")
    parser.add_argument("--from", dest="start", help="Start at the first line containing this text")
    parser.add_argument("--static", action="store_true", help="Final frame only, no animation")
    argv = sys.argv[1:]
    split = argv.index("--") if "--" in argv else len(argv)
    args = parser.parse_args(argv[:split])
    command = argv[split + 1 :] or [
        sys.executable,
        "-m",
        "outfence",
        "demo",
        "--output",
        "runs/demo",
    ]
    svg = render(
        capture(command, args.columns), args.title, args.prompt, not args.static, args.start
    )
    Path(args.output).write_text(svg, encoding="utf-8")
    print(f"Wrote {args.output} ({len(svg) // 1024} KB)")


if __name__ == "__main__":
    main()
