"""Interactive terminal look: brand colors, the Capitoline goose and live decisions.

Styling applies only when stdout is a terminal, or when OUTFENCE_COLOR=always. NO_COLOR,
OUTFENCE_COLOR=never, pipes, files and CI get the plain report, which carries the same facts.
"""

import os
import re
import threading
import time
from datetime import datetime

from .mascot import MARK, POSES
from .report import EXIT_REASONS, explain, terminal_text

# Copied from brand/tokens.json; tests/test_console.py keeps them identical.
INK, PAPER, ACID, MIST, SLATE = "#171917", "#FAFAF7", "#D9F378", "#C2C6BC", "#656B63"
# On dark terminals the outlines turn dark grey and the white body carries the shape.
DARK_OUTLINE, DARK_SHADOW, LIGHT_SHADOW = "#5A5F58", "#30332F", "#D0D4CB"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
GLYPHS = {
    "o": [".....", ".....", ".###.", "#...#", "#...#", "#...#", ".###."],
    "u": [".....", ".....", "#...#", "#...#", "#...#", "#..##", ".##.#"],
    "t": [".#...", ".#...", "####.", ".#...", ".#...", ".#..#", "..##."],
    "f": ["..###", ".#...", "####.", ".#...", ".#...", ".#...", ".#..."],
    "e": [".....", ".....", ".###.", "#...#", "#####", "#....", ".###."],
    "n": [".....", ".....", "####.", "#...#", "#...#", "#...#", "#...#"],
    "c": [".....", ".....", ".###.", "#...#", "#....", "#...#", ".###."],
}
LABELS = {"allowed": "ALLOWED", "blocked": "BLOCKED", "would_block": "WOULD BLOCK"}
WIDTH = 13


def xterm(r, g, b):
    """Nearest xterm-256 color, for terminals without 24-bit color."""
    if max(r, g, b) - min(r, g, b) < 16:
        level = (r + g + b) // 3
        return 16 if level < 8 else 231 if level > 247 else 232 + (level - 8) // 10
    return 16 + 36 * round(r / 51) + 6 * round(g / 51) + round(b / 51)


class Style:
    def __init__(self, enabled=False, truecolor=True, light=False):
        self.enabled, self.truecolor, self.light = enabled, truecolor, light
        self.text = INK if light else PAPER
        self.dim = SLATE if light else MIST

    def color(self, hex_color, layer):
        r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
        if self.truecolor:
            return f"\x1b[{layer};2;{r};{g};{b}m"
        return f"\x1b[{layer};5;{xterm(r, g, b)}m"

    def paint(self, text, fg=None, bg=None, bold=False):
        if not self.enabled:
            return text
        codes = (self.color(fg, 38) if fg else "") + (self.color(bg, 48) if bg else "")
        codes += "\x1b[1m" if bold else ""
        return f"{codes}{text}\x1b[0m" if codes else text

    def palette(self, art):
        if art == "mark":
            return (
                {"k": INK, "w": PAPER, "a": ACID}
                if self.light
                else {"k": PAPER, "w": INK, "a": ACID}
            )
        if self.light:
            return {"k": INK, "w": PAPER, "a": ACID, "s": LIGHT_SHADOW}
        return {"k": DARK_OUTLINE, "w": PAPER, "a": ACID, "s": DARK_SHADOW}


def detect(stream, environ=None):
    environ = os.environ if environ is None else environ
    choice = environ.get("OUTFENCE_COLOR", "auto").lower()
    tty = getattr(stream, "isatty", lambda: False)()
    if environ.get("NO_COLOR") or choice == "never":
        return Style()
    if choice != "always" and (not tty or environ.get("TERM") == "dumb"):
        return Style()
    truecolor = environ.get("COLORTERM", "").lower() in ("truecolor", "24bit")
    theme = environ.get("OUTFENCE_THEME", "").lower()
    background = environ.get("COLORFGBG", "").rsplit(";", 1)[-1]
    return Style(
        True, truecolor, theme == "light" or (theme != "dark" and background in ("7", "15"))
    )


def visible(text):
    return len(ANSI.sub("", text))


def decode(art):
    return [
        "".join(c * int(n or 1) for n, c in re.findall(r"(\d*)([kwas.])", row))
        for row in art.split("|")
    ]


def crop(rows):
    used = [i for i, row in enumerate(rows) if set(row) != {"."}]
    cols = [j for j in range(len(rows[0])) if any(row[j] != "." for row in rows)]
    return [row[cols[0] : cols[-1] + 1] for row in rows[used[0] : used[-1] + 1]]


def pixels(style, rows, palette):
    """Two tile rows per line: the upper half block takes the foreground, the lower the background."""
    if len(rows) % 2:
        rows = rows + ["." * len(rows[0])]
    lines = []
    for top, bottom in zip(rows[0::2], rows[1::2]):
        cells = []
        for a, b in zip(top, bottom):
            if a == b == ".":
                cells.append((" ", None, None))
            elif b == ".":
                cells.append(("▀", palette[a], None))
            elif a == ".":
                cells.append(("▄", palette[b], None))
            else:
                cells.append(("▀", palette[a], palette[b]))
        line, start = "", 0
        for index in range(1, len(cells) + 1):
            if index == len(cells) or cells[index][1:] != cells[start][1:]:
                text = "".join(cell[0] for cell in cells[start:index])
                line += style.paint(text, *cells[start][1:]) if cells[start][1] else text
                start = index
        lines.append(line.rstrip())
    return lines


def wordmark(style):
    rows = [""] * 7
    for index, letter in enumerate("outfence"):
        rows = [row + ("." if index else "") + glyph for row, glyph in zip(rows, GLYPHS[letter])]
    return pixels(style, [row.replace("#", "k") for row in rows], {"k": style.text})


def side_by_side(left, right, gap=3):
    width = max((visible(line) for line in left), default=0)
    height = max(len(left), len(right))
    left, right = left + [""] * (height - len(left)), right + [""] * (height - len(right))
    return [f"  {a}{' ' * (width - visible(a) + gap)}{b}".rstrip() for a, b in zip(left, right)]


def banner(style, status, columns):
    if columns < 72:
        return [
            f"  {style.paint('outfence', style.text, bold=True)}  {style.paint(status, style.dim)}"
        ]
    right = wordmark(style) + [
        style.paint("Know where your agents connect.", style.dim),
        style.paint(status, style.dim),
    ]
    return side_by_side(pixels(style, decode(MARK), style.palette("mark")), right)


def label(style, action):
    word = LABELS.get(action, terminal_text(action).upper())
    if action == "blocked":
        return style.paint(f" {word} ", INK, ACID, bold=True) + " " * (WIDTH - len(word) - 2)
    if action == "would_block":
        return style.paint(word.ljust(WIDTH), ACID, bold=True)
    return style.paint(word.ljust(WIDTH), style.dim)


def destination(event):
    host = event["host"] or "unknown"
    return terminal_text(
        f"[{host}]:{event['port']}" if ":" in host else f"{host}:{event['port'] or '?'}"
    )


class Live:
    """Prints decisions and tool changes as they happen. Proxy and tap threads call it."""

    def __init__(self, style, stream):
        self.style, self.stream, self.lock = style, stream, threading.Lock()

    def line(self, kind, text):
        stamp = self.style.paint(time.strftime("%H:%M:%S"), self.style.dim)
        with self.lock:
            print(f"  {stamp}  {kind}{text}", file=self.stream, flush=True)

    def decision(self, event):
        reason = self.style.paint(terminal_text(event["reason"]), self.style.dim)
        self.line(label(self.style, event["action"]), f"{destination(event)}  {reason}")

    def change(self, note):
        kind = self.style.paint(note["kind"].replace("_", " ").ljust(WIDTH), self.style.dim)
        if note["kind"] == "tools":
            names = [f"+{n}" for n in note["added"]] + [f"-{n}" for n in note["removed"]]
            self.line(kind, terminal_text(" ".join(names)))
        else:
            hosts = self.style.paint(terminal_text(", ".join(note["hosts"])), self.style.dim)
            self.line(kind, f"{terminal_text(note['name'] or 'unnamed')}  {hosts}")


def pose_for(report):
    actions = {event["action"] for event in report["events"]}
    if "blocked" in actions:
        return "blocking"
    if "would_block" in actions or report["exit_code"] == 3:
        return "alarm"
    return "approving" if report["events"] else "idle"


def plural(count, word):
    return f"{count} {word}{'' if count == 1 else 's'}"


def headline(style, report):
    events = report["events"]
    blocked = sum(e["action"] == "blocked" for e in events)
    would = sum(e["action"] == "would_block" for e in events)
    model = [e for e in events if e.get("origin") == "model" and e["action"] != "allowed"]
    only = all(len(e.get("named_by") or ()) <= 1 for e in model)
    by_model = f", {len(model)} named {'only' if only else 'first'} by the model" if model else ""
    if blocked:
        return f"{label(style, 'blocked')}{plural(blocked, 'destination')} outside your policy{by_model}"
    if would:
        text = f"{plural(would, 'destination')} outside your policy, let through by observe mode"
        return f"{label(style, 'would_block')}{text}{by_model}"
    if report["exit_code"] == 3:
        return f"{style.paint('INCOMPLETE'.ljust(WIDTH), ACID, bold=True)}evidence may be missing"
    if events:
        return (
            f"{label(style, 'allowed')}{plural(len(events), 'destination')}, all within your policy"
        )
    return f"{style.paint('IDLE'.ljust(WIDTH), style.dim)}no proxy requests observed"


def render(style, report, evidence, columns, environ=None):
    """The styled report: the same facts as format_report, plus the goose for the outcome."""
    environ = os.environ if environ is None else environ
    dim = style.dim
    events, tap, coverage = report["events"], report.get("model_tap"), report["coverage"]
    counts = {
        a: sum(e["action"] == a for e in events) for a in ("allowed", "blocked", "would_block")
    }
    exit_code = report["exit_code"]
    workload = report["workload_exit_code"]
    summary = [
        "",
        headline(style, report),
        "",
        f"allowed {counts['allowed']} | blocked {counts['blocked']} | would block {counts['would_block']}",
        style.paint(
            f"mode {report['mode']} | coverage {coverage['status']}"
            f" | provenance {coverage.get('provenance', 'unavailable')}",
            dim,
        ),
        "",
        f"{style.paint(f'Exit {exit_code}', style.text, bold=True)}  {EXIT_REASONS[exit_code]}",
        style.paint(
            f"workload exit {workload if workload is not None else 'unavailable'}"
            " | task correctness not evaluated",
            dim,
        ),
        style.paint(f"evidence {evidence}", dim),
    ]
    goose = []
    if environ.get("OUTFENCE_GOOSE", "on").lower() not in ("off", "0", "no"):
        goose = pixels(style, crop(decode(POSES[pose_for(report)])), style.palette("pose"))
    width = max((visible(line) for line in goose), default=0)
    if goose and columns >= width + 5 + max(visible(line) for line in summary):
        lines = side_by_side(goose, summary)
    elif goose and columns >= width + 4:
        lines = [f"  {line}" for line in goose] + [f"  {line}" for line in summary]
    else:
        lines = [f"  {line}" for line in summary]
    lines.append("")
    if tap is not None:
        lines.append(
            "  "
            + style.paint("model tap".ljust(WIDTH), dim)
            + f"{plural(tap['requests'], 'chat request')} | {plural(len(tap['tool_calls']), 'tool call')}"
            + f" | {tap['rejected']} rejected | {tap['errors']} errors"
        )
        for change in tap["environment"]:
            names = [f"+{n}" for n in change["added"]] + [f"-{n}" for n in change["removed"]]
            if names:
                when = datetime.fromisoformat(change["time"]).astimezone().strftime("%H:%M:%S")
                kind = style.paint("tools".ljust(WIDTH), dim)
                lines.append(f"  {kind}{when}  {terminal_text(' '.join(names))}")
        lines.append("")
    for event in events:
        reason = f"{terminal_text(event['reason'])} | {terminal_text(event['connection'])}"
        lines.append(
            f"  {label(style, event['action'])}{destination(event)}  {style.paint(reason, dim)}"
        )
        lines.extend(" " * (WIDTH + 2) + style.paint(line.strip(), dim) for line in explain(event))
    if not events:
        lines.append(
            "  "
            + style.paint(
                "No proxy requests observed. This does not prove there was no network activity.",
                dim,
            )
        )
    lines += [
        "",
        "  "
        + style.paint(
            f"Dropped events: {coverage['dropped_events']}. Direct connections bypass this proxy."
            " Encrypted contents are not inspected.",
            dim,
        ),
    ]
    return "\n".join(lines)
