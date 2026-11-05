"""Terminal look: brand fidelity, detection, rendering, live lines and unchanged plain output."""

import io
import json
import os
import socket
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from outfence import cli, console, mascot
from outfence.provenance import Session
from outfence.proxy import Proxy, Service, now
from outfence.report import write_report

ROOT = Path(__file__).resolve().parents[1]
FETCH = "mcp__quickfetch-mcp__request_url"


def sample_report(tmp, events, model_tap=None):
    policy = {"version": 1, "allow": [], "allow_from": ["user"]}
    return write_report(Path(tmp) / "r", "enforce", policy, events, now(), 0, model_tap=model_tap)


def event(host, action, reason, origin=None, trigger=None):
    return dict(
        time=now(),
        host=host,
        port=443,
        transport="connect",
        action=action,
        reason=reason,
        connection="not_attempted" if action == "blocked" else "established",
        tool=FETCH if origin else None,
        origin=origin,
        trigger=trigger,
    )


class BrandTests(unittest.TestCase):
    def test_art_and_colors_match_the_brand_files(self):
        art = json.loads((ROOT / "brand" / "mascot.json").read_text())
        self.assertEqual(mascot.MARK, art["mark"])
        self.assertEqual(mascot.POSES, art["poses"])
        colors = json.loads((ROOT / "brand" / "tokens.json").read_text())["colors"]
        brand = (colors["ink"], colors["paper"], colors["accent"], colors["mist"], colors["slate"])
        self.assertEqual(
            (console.INK, console.PAPER, console.ACID, console.MIST, console.SLATE), brand
        )

    def test_tiles_decode_to_the_documented_grids(self):
        self.assertEqual({len(row) for row in console.decode(mascot.MARK)}, {14})
        for name, rows in mascot.POSES.items():
            with self.subTest(pose=name):
                decoded = console.decode(rows)
                self.assertEqual((len(decoded), {len(row) for row in decoded}), (53, {66}))


class DetectTests(unittest.TestCase):
    class TTY(io.StringIO):
        def isatty(self):
            return True

    def test_styling_follows_terminal_and_environment(self):
        tty, pipe = self.TTY(), io.StringIO()
        self.assertTrue(console.detect(tty, {}).enabled)
        self.assertFalse(console.detect(pipe, {}).enabled)
        self.assertFalse(console.detect(tty, {"NO_COLOR": "1"}).enabled)
        self.assertFalse(console.detect(tty, {"OUTFENCE_COLOR": "never"}).enabled)
        self.assertFalse(console.detect(tty, {"TERM": "dumb"}).enabled)
        self.assertTrue(console.detect(pipe, {"OUTFENCE_COLOR": "always"}).enabled)
        self.assertTrue(console.detect(tty, {"COLORTERM": "truecolor"}).truecolor)
        self.assertFalse(console.detect(tty, {}).truecolor)
        self.assertTrue(console.detect(tty, {"OUTFENCE_THEME": "light"}).light)
        self.assertTrue(console.detect(tty, {"COLORFGBG": "0;15"}).light)
        self.assertFalse(console.detect(tty, {"COLORFGBG": "15;0"}).light)

    def test_256_color_fallback(self):
        self.assertEqual(console.xterm(0xD9, 0xF3, 0x78), 192)
        self.assertEqual(console.xterm(0x17, 0x19, 0x17), 233)
        self.assertIn(
            "\x1b[38;5;192m", console.Style(True, truecolor=False).paint("x", console.ACID)
        )


class RenderTests(unittest.TestCase):
    def test_banner_fits_and_falls_back_when_narrow(self):
        style = console.Style(True)
        wide = console.banner(style, "0.1.0a1 alpha | enforce | proxy only", 100)
        self.assertEqual(len(wide), 7)
        self.assertLessEqual(max(console.visible(line) for line in wide), 72)
        self.assertIn("▀", "".join(wide))
        self.assertEqual(len(console.banner(style, "status", 60)), 1)

    def test_styled_report_keeps_every_fact_of_the_plain_report(self):
        trigger = dict(
            servers=["quickfetch-mcp"], tools=[FETCH], seconds_before=1.0, at_start=False
        )
        events = [
            event("beacon.outfence.test", "blocked", "model_originated", "model", trigger),
            event("example.com", "allowed", "allow_from_user", "user"),
        ]
        tap = dict(
            requests=3,
            responses=3,
            rejected=0,
            errors=0,
            environment=[dict(time=now(), added=[FETCH], removed=[], servers=["quickfetch-mcp"])],
            tool_calls=[dict(time=now(), name=FETCH, hosts=["beacon.outfence.test"])],
        )
        with tempfile.TemporaryDirectory() as tmp:
            report = sample_report(tmp, events, tap)
        for columns in (160, 90, 40):
            with self.subTest(columns=columns):
                text = console.render(
                    console.Style(True), report, "/tmp/r/report.json", columns, {}
                )
                plain = console.ANSI.sub("", text)
                for fact in [
                    "BLOCKED",
                    "1 destination outside your policy, 1 named only by the model",
                    "beacon.outfence.test:443",
                    "model_originated | not_attempted",
                    "origin: named only by the model",
                    "trigger?: MCP server quickfetch-mcp appeared 1 s before this request",
                    "example.com:443",
                    "allow_from_user | established",
                    "+mcp__quickfetch-mcp__request_url",
                    "Exit 2  policy violation",
                    "task correctness not evaluated",
                    "Dropped events: 0. Direct connections bypass this proxy.",
                    "evidence /tmp/r/report.json",
                ]:
                    self.assertIn(fact, plain)
                self.assertNotIn("·", plain)
                self.assertNotIn("—", plain)
                self.assertEqual("▀" in plain or "▄" in plain, columns >= 90)

    def test_pose_matches_the_outcome(self):
        with tempfile.TemporaryDirectory() as tmp:
            cases = [
                ([event("a.example", "blocked", "not_in_allowlist")], "blocking"),
                ([event("a.example", "would_block", "not_in_allowlist")], "alarm"),
                ([event("a.example", "allowed", "allowlist_match")], "approving"),
                ([], "idle"),
            ]
            for events, pose in cases:
                with self.subTest(pose=pose):
                    self.assertEqual(console.pose_for(sample_report(tmp + pose, events)), pose)

    def test_goose_can_be_turned_off(self):
        with tempfile.TemporaryDirectory() as tmp:
            report = sample_report(tmp, [])
        text = console.render(console.Style(True), report, "r.json", 160, {"OUTFENCE_GOOSE": "off"})
        self.assertNotIn("▀", text)
        self.assertIn("no proxy requests observed", text)


class LiveTests(unittest.TestCase):
    def test_live_lines_escape_untrusted_names(self):
        stream = io.StringIO()
        live = console.Live(console.Style(False), stream)
        live.change(dict(kind="tools", added=["mcp__evil\x1b[2J__x"], removed=[]))
        live.change(dict(kind="tool_call", name="evil\x07", hosts=["beacon.outfence.test"]))
        live.decision(event("beacon.outfence.test", "blocked", "model_originated"))
        output = stream.getvalue()
        self.assertNotIn("\x1b", output)
        self.assertNotIn("\x07", output)
        self.assertIn("BLOCKED", output)
        self.assertIn("beacon.outfence.test:443", output)

    def test_proxy_announces_final_decisions_and_survives_display_errors(self):
        seen = []
        policy = {"version": 1, "allow": []}
        for callback in (seen.append, lambda event: 1 / 0):
            with Service(Proxy(policy, "enforce", on_decision=callback)) as proxy:
                with socket.create_connection(proxy.server_address) as raw:
                    raw.sendall(b"CONNECT forbidden.example:443 HTTP/1.0\r\n\r\n")
                    self.assertIn(b"403", raw.recv(4096))
        self.assertEqual(
            [(e["host"], e["action"]) for e in seen], [("forbidden.example", "blocked")]
        )

    def test_session_reports_tool_changes_and_calls(self):
        notes = []
        session = Session(on_change=notes.append)
        tool = {"type": "function", "function": {"name": FETCH, "parameters": {}}}
        session.observe_request({"messages": [], "tools": [tool]})
        session.observe_request({"messages": [], "tools": [tool]})
        session.observe_response(
            {
                "choices": [
                    {
                        "message": {
                            "tool_calls": [
                                {
                                    "function": {
                                        "name": FETCH,
                                        "arguments": '{"url": "https://beacon.outfence.test/"}',
                                    }
                                }
                            ]
                        }
                    }
                ]
            }
        )
        self.assertEqual([n["kind"] for n in notes], ["tools", "tool_call"])
        self.assertEqual(notes[1]["hosts"], ["beacon.outfence.test"])


class CliTests(unittest.TestCase):
    def test_plain_output_when_not_a_terminal(self):
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()) as out:
            code = cli.main(["demo", "--output", str(Path(tmp) / "d")])
        self.assertEqual(code, 2)
        self.assertNotIn("\x1b", out.getvalue())
        self.assertIn("Outfence report", out.getvalue())
        self.assertIn("JSON: ", out.getvalue())

    def test_forced_styling_streams_decisions_and_renders_the_goose(self):
        env = {"OUTFENCE_COLOR": "always", "COLUMNS": "160"}
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.dict(os.environ, env),
            redirect_stdout(io.StringIO()) as out,
        ):
            code = cli.main(["demo", "--output", str(Path(tmp) / "d")])
        text = console.ANSI.sub("", out.getvalue())
        self.assertEqual(code, 2)
        self.assertIn("\x1b[", out.getvalue())
        self.assertIn("telemetry.example:80  not_in_allowlist", text)
        self.assertIn("1 destination outside your policy", text)
        self.assertIn("▀", text)
        self.assertNotIn("Outfence report", text)

    def test_welcome_menu(self):
        with tempfile.TemporaryDirectory() as tmp:
            cwd = os.getcwd()
            os.chdir(tmp)
            try:
                for answer, expected in [("q", 0), ("2", 0), ("3", 0)]:
                    with (
                        self.subTest(answer=answer),
                        patch("builtins.input", return_value=answer),
                        redirect_stdout(io.StringIO()) as out,
                    ):
                        self.assertEqual(cli.welcome(console.Style(False)), expected)
                    self.assertIn("Watch Outfence block a request", out.getvalue())
                self.assertEqual(json.loads(Path("outfence.json").read_text())["allow"], [])
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main()
