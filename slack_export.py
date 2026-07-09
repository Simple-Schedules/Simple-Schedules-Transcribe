"""
Auto-share a finished transcription's Markdown into a Slack channel.

On completion the app calls post_to_slack(json_path); this renders the
transcription to Markdown (reusing meet_export.render_markdown) and uploads it
as a .md file attachment to the configured channel — by default #möte.

Design notes:
- FAIL-SAFE: like the Meet export, this is a nice-to-have on top of the core
  transcription. It must never raise into the transcription flow — the caller
  wraps it, and it also guards internally. Any failure prints a note and returns.
- NO SECRETS IN GIT: the token is read from the SS_SLACK_TOKEN env var, or from a
  [slack] section in settings.ini (which is .gitignored). If no token is
  configured, the export is skipped silently — safe default on every machine.
- POSTS AS WHOEVER OWNS THE TOKEN: a Slack *user* token (xoxp-...) posts as that
  user; a *bot* token (xoxb-...) posts as the app. Either works — file upload
  needs the `files:write` scope (and `chat:write`).
- Uses Slack's current external-upload flow (files.getUploadURLExternal ->
  upload -> files.completeUploadExternal); the legacy files.upload is deprecated.
"""

from __future__ import annotations

import os
import io
import json
import configparser
from pathlib import Path

import requests

# #möte in the Simple Schedules workspace. Override with SS_SLACK_CHANNEL or the
# [slack] channel setting.
DEFAULT_CHANNEL = "C0B6AF6BQCB"

_API = "https://slack.com/api"


def _settings_path() -> Path:
    return Path(__file__).resolve().parent / "settings.ini"


def _config(key: str, env: str) -> str | None:
    """Resolve a value from the environment first, then settings.ini [slack]."""
    val = os.environ.get(env)
    if val:
        return val.strip()
    try:
        cfg = configparser.ConfigParser()
        if cfg.read(_settings_path()) and cfg.has_option("slack", key):
            got = cfg.get("slack", key).strip()
            return got or None
    except Exception:
        pass
    return None


def _render_markdown(data: dict) -> str:
    """Reuse the Meet-repo renderer so Slack and Meet notes stay identical."""
    from meet_export import render_markdown, _safe_title  # local import: fail-safe
    return render_markdown(data)


def _safe_stem(title: str) -> str:
    from meet_export import _safe_title
    return _safe_title(title)


def post_to_slack(json_path: str) -> bool:
    """
    Render a saved transcription.json to Markdown and upload it to Slack.
    Returns True on a confirmed post, False if skipped or failed. Never raises.
    """
    try:
        token = _config("token", "SS_SLACK_TOKEN")
        if not token:
            print("[slack_export] No Slack token configured — skipping Slack post.")
            return False
        channel = _config("channel", "SS_SLACK_CHANNEL") or DEFAULT_CHANNEL

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        title = data.get("title") or "Transcription"
        md_text = _render_markdown(data).encode("utf-8")
        filename = f"{_safe_stem(title)}.md"
        comment = f"🎙️ New transcript: *{title}*"

        headers = {"Authorization": f"Bearer {token}"}

        # 1) Reserve an upload URL for the file.
        r1 = requests.post(
            f"{_API}/files.getUploadURLExternal",
            headers=headers,
            data={"filename": filename, "length": len(md_text)},
            timeout=30,
        )
        j1 = r1.json()
        if not j1.get("ok"):
            print(f"[slack_export] getUploadURLExternal failed: {j1.get('error')}")
            return False
        upload_url = j1["upload_url"]
        file_id = j1["file_id"]

        # 2) PUT/POST the raw bytes to the reserved URL.
        r2 = requests.post(
            upload_url,
            files={"file": (filename, io.BytesIO(md_text), "text/markdown")},
            timeout=60,
        )
        if r2.status_code != 200:
            print(f"[slack_export] file upload HTTP {r2.status_code}")
            return False

        # 3) Complete the upload and share it into the channel.
        r3 = requests.post(
            f"{_API}/files.completeUploadExternal",
            headers={**headers, "Content-Type": "application/json; charset=utf-8"},
            data=json.dumps({
                "files": [{"id": file_id, "title": title}],
                "channel_id": channel,
                "initial_comment": comment,
            }),
            timeout=30,
        )
        j3 = r3.json()
        if not j3.get("ok"):
            print(f"[slack_export] completeUploadExternal failed: {j3.get('error')}")
            return False

        print(f"[slack_export] Shared '{filename}' to Slack channel {channel}.")
        return True
    except Exception as e:  # never break the transcription flow
        print(f"[slack_export] Slack post skipped ({e}).")
        return False
