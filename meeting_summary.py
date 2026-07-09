"""
Fill in a transcript's Summary / Decisions / Action items using Claude Code.

Instead of the paid Anthropic API, this shells out to the `claude` CLI in
headless one-shot mode (`claude -p`), which runs on the user's Claude Code
subscription — no API key, no per-call charge. It asks Claude for a JSON object
(summary + decisions + action_items) and writes those fields back into the saved
transcription.json, so meet_export / slack_export render filled-in sections.

Design notes:
- FAIL-SAFE: a nice-to-have on top of the transcription. Never raises into the
  pipeline; on any failure it prints a note and leaves the transcript unchanged.
- Detached/launchd launches don't inherit the shell PATH, so we resolve the
  `claude` binary from its known install locations (~/.local/bin etc.).
- Runs in a throwaway working directory so Claude Code doesn't pick up this repo's
  CLAUDE.md / project context — we just want a clean one-shot answer.
- Values come back in the transcript's own language (we tell Claude to match it).
"""

from __future__ import annotations

import os
import json
import shutil
import tempfile
import subprocess
from pathlib import Path


def _claude_bin() -> str | None:
    """Locate the Claude Code CLI, tolerating GUI launches without a shell PATH."""
    found = shutil.which("claude")
    if found:
        return found
    candidates = [
        Path.home() / ".local" / "bin" / "claude",
        Path("/opt/homebrew/bin/claude"),
        Path("/usr/local/bin/claude"),
        Path.home() / ".claude" / "local" / "claude",
    ]
    for c in candidates:
        if c.is_file() and os.access(c, os.X_OK):
            return str(c)
    return None


def _transcript_text(data: dict) -> str:
    speakers = data.get("speakers", []) or []
    lines = []
    for entry in data.get("transcribedText", []) or []:
        idx = entry.get("speakerIndex", 0)
        speaker = speakers[idx] if isinstance(idx, int) and idx < len(speakers) else f"Speaker {int(idx) + 1}"
        text = entry.get("text", "")
        if text:
            lines.append(f"{speaker}: {text}")
    return "\n".join(lines)


_PROMPT = """You are summarizing a meeting transcript. Respond with ONLY a JSON \
object — no markdown, no code fences, no commentary — with exactly these keys:
- "summary": a concise 2-4 sentence summary of the meeting
- "decisions": an array of short strings, the concrete decisions made (empty array if none)
- "action_items": an array of short strings, the action items / to-dos, each ideally \
naming the owner if it's clear (empty array if none)

Write every value in the SAME language as the transcript. Do not invent content \
that isn't supported by the transcript.

Transcript:
"""


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        # drop the opening fence line (``` or ```json) and the closing fence
        t = t.split("\n", 1)[1] if "\n" in t else t
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    return t.strip()


def enrich_json(json_path: str, timeout: float = 240.0) -> bool:
    """Add summary/decisions/actionItems to a saved transcription.json via Claude
    Code. Returns True if it enriched the file, False if skipped/failed. Never raises."""
    try:
        claude = _claude_bin()
        if not claude:
            print("[meeting_summary] Claude Code CLI not found — skipping summary.")
            return False

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        transcript = _transcript_text(data)
        if not transcript.strip():
            print("[meeting_summary] Empty transcript — skipping summary.")
            return False

        # Neutral cwd so Claude Code doesn't load this repo's project context.
        workdir = tempfile.mkdtemp(prefix="ss-summary-")
        try:
            proc = subprocess.run(
                [claude, "-p", "--output-format", "json"],
                input=_PROMPT + transcript,
                capture_output=True, text=True, timeout=timeout, cwd=workdir,
            )
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        if proc.returncode != 0:
            print(f"[meeting_summary] claude -p failed (rc={proc.returncode}): {proc.stderr.strip()[:200]}")
            return False

        envelope = json.loads(proc.stdout)
        if envelope.get("is_error"):
            print(f"[meeting_summary] claude reported an error: {envelope.get('result', '')[:200]}")
            return False

        result = _strip_fences(str(envelope.get("result", "")))
        parsed = json.loads(result)

        summary = str(parsed.get("summary", "")).strip()
        decisions = [str(d).strip() for d in (parsed.get("decisions") or []) if str(d).strip()]
        actions = [str(a).strip() for a in (parsed.get("action_items") or []) if str(a).strip()]

        data["summary"] = summary
        data["decisions"] = decisions
        data["actionItems"] = actions

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"[meeting_summary] Enriched: {len(decisions)} decision(s), {len(actions)} action(s).")
        return True
    except Exception as e:  # never break the transcription flow
        print(f"[meeting_summary] Summary skipped ({e}).")
        return False
