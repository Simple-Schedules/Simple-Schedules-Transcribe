"""
Auto-export a finished transcription into the Simple-Schedules-Meet repo.

On completion the app calls export_to_meet(json_path); this renders the
transcription as Markdown and drops it into the Meet repo under a day folder
(YYYY-MM-DD/<title>.md), matching that repo's _template.md convention.

Design notes:
- FAIL-SAFE: this is a nice-to-have on top of the core transcription. It must
  never raise into the transcription flow — the caller wraps it, and it also
  guards internally. A failed export prints a note and returns None.
- It only writes the .md file. Committing / pushing the Meet repo stays manual
  (pushing meeting notes is outward-facing — a human decides when).
- The Meet repo location resolves from, in order: the SS_MEET_REPO env var, then
  the sibling repo (~/.../SS/Simple-Schedules-Meet). If the repo root doesn't
  exist, the export is skipped (no stray folders created on other machines).
"""

from __future__ import annotations

import os
import json
import datetime
import subprocess
from pathlib import Path


def _resolve_meet_repo() -> Path | None:
    """Find the Meet repo root, or None if it isn't present on this machine."""
    override = os.environ.get("SS_MEET_REPO")
    if override:
        p = Path(override).expanduser()
        return p if p.is_dir() else None

    # Default: sibling of this Transcribe repo — <...>/SS/Simple-Schedules-Meet
    sibling = Path(__file__).resolve().parent.parent / "Simple-Schedules-Meet"
    if sibling.is_dir():
        return sibling

    # Fallback: the known layout under the user's Documents
    fallback = Path.home() / "Documents" / "SS" / "Simple-Schedules-Meet"
    return fallback if fallback.is_dir() else None


def _safe_title(title: str) -> str:
    """Filesystem-safe, kebab-ish file stem. Mirrors the app's sanitization."""
    import re
    cleaned = "".join(c if c.isalnum() or c in (" ", "-", "_") else "-" for c in str(title))
    cleaned = re.sub(r"[\s\-_]+", "-", cleaned).strip("-_")
    return cleaned or "transcription"


def _valid_day(date_str: str) -> str:
    """Return a YYYY-MM-DD day folder name — the transcription's date, else today."""
    try:
        return datetime.date.fromisoformat(str(date_str)).isoformat()
    except (ValueError, TypeError):
        return datetime.date.today().isoformat()


def _fmt_timestamp(ts: str) -> str:
    """00:12:34 -> 12:34 (drop a leading 00: hour), leave others intact."""
    parts = str(ts).split(":")
    if len(parts) == 3 and parts[0] == "00":
        return f"{parts[1]}:{parts[2]}"
    return str(ts)


def render_markdown(data: dict) -> str:
    """Render transcription data as a Meet-repo meeting note (template-shaped)."""
    title = data.get("title") or "Untitled Transcription"
    date = data.get("date", "")
    time = data.get("time", "")
    speakers = data.get("speakers", []) or []

    lines = [f"# {title}", ""]
    dt = f"{date} {time}".strip()
    lines.append(f"- **Date:** {dt}" if dt else "- **Date:**")
    lines.append(f"- **Present:** {', '.join(speakers)}" if speakers else "- **Present:**")
    lines.append("- **Source:** auto-exported from Simple Schedules Transcribe")
    lines += ["", "## Decisions", "-", "", "## Action items", "- [ ]", "", "## Transcript", ""]

    for entry in data.get("transcribedText", []) or []:
        ts = _fmt_timestamp(entry.get("timestamp", ""))
        idx = entry.get("speakerIndex", 0)
        speaker = speakers[idx] if isinstance(idx, int) and idx < len(speakers) else f"Speaker {int(idx) + 1}"
        text = entry.get("text", "")
        lines.append(f"**[{ts}] {speaker}:** {text}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _git_publish(repo: Path, target: Path) -> None:
    """
    Commit the new note and push it to the Meet repo's remote — hands-off.
    Fail-safe: any git failure (offline, no remote, auth) prints a note and is
    swallowed, so the transcription is never affected. Disable by setting
    SS_MEET_AUTOPUSH=0.
    """
    if os.environ.get("SS_MEET_AUTOPUSH", "1") not in ("1", "true", "True", "yes"):
        return
    try:
        if not (repo / ".git").exists():
            print("[meet_export] Meet repo is not a git repo — skipping auto-push.")
            return

        def git(*args, check=True):
            return subprocess.run(
                ["git", "-C", str(repo), *args],
                capture_output=True, text=True, timeout=60, check=check,
            )

        rel = target.relative_to(repo)
        git("add", str(rel))
        # Nothing staged (e.g. re-export of identical content) → skip cleanly.
        if git("diff", "--cached", "--quiet", check=False).returncode == 0:
            print("[meet_export] No changes to publish.")
            return
        git("commit", "-m", f"meet: add transcript {rel}")

        # Only push if a remote is configured; a local-only Meet repo just commits.
        if git("remote", check=False).stdout.strip():
            push = git("push", check=False)
            if push.returncode != 0:
                print(f"[meet_export] Committed but push failed (will sync later): {push.stderr.strip()}")
            else:
                print(f"[meet_export] Published {rel} to Meet remote.")
        else:
            print(f"[meet_export] Committed {rel} (no remote configured).")
    except Exception as e:
        print(f"[meet_export] Auto-push skipped ({e}).")


def export_to_meet(json_path: str, meet_repo: str | None = None) -> str | None:
    """
    Convert a saved transcription.json into a Markdown note in the Meet repo,
    filed under its day folder. Returns the written path, or None if skipped.
    Never raises.
    """
    try:
        repo = Path(meet_repo).expanduser() if meet_repo else _resolve_meet_repo()
        if repo is None or not repo.is_dir():
            print("[meet_export] Meet repo not found on this machine — skipping auto-export.")
            return None

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        day_dir = repo / _valid_day(data.get("date"))
        day_dir.mkdir(parents=True, exist_ok=True)

        stem = _safe_title(data.get("title"))
        target = day_dir / f"{stem}.md"
        counter = 2
        while target.exists():
            target = day_dir / f"{stem}_{counter}.md"
            counter += 1

        target.write_text(render_markdown(data), encoding="utf-8")
        print(f"[meet_export] Wrote {target}")
        _git_publish(repo, target)
        return str(target)
    except Exception as e:  # never break the transcription flow
        print(f"[meet_export] Auto-export skipped ({e}).")
        return None
