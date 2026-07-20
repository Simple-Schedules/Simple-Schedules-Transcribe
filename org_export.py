"""
Push a finished transcription into Simple Org.

Runs alongside meet_export (markdown in the Meet repo) and slack_export — it
does not replace either. The git copy stays the durable one; this is what makes
meetings searchable from the phone.

Never raises: a transcription must never be lost because a network call failed.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

ENDPOINT = os.environ.get(
    "SS_ORG_ENDPOINT", "https://org.simpleschedules.se/api/transcripts/ingest"
)


def _token() -> str | None:
    """Shared secret. Env first, then settings.ini, so neither is required."""
    tok = os.environ.get("SS_ORG_TOKEN")
    if tok:
        return tok.strip()
    try:
        import configparser
        from pathlib import Path

        cfg = configparser.ConfigParser()
        cfg.read(Path(__file__).with_name("settings.ini"), encoding="utf-8")
        return (cfg.get("simple_org", "token", fallback="") or "").strip() or None
    except Exception:
        return None


def _met_at(data: dict) -> str:
    """`2026-07-20` + `14:30` -> an ISO timestamp the database will accept."""
    date = (data.get("date") or "").strip()
    time = (data.get("time") or "").strip() or "12:00"
    if not date:
        return ""
    if len(time) == 5:
        time += ":00"
    return f"{date}T{time}"


def _audio_path(json_path: str, data: dict):
    """Resolve `audioPath` (relative to the transcription folder) to a real file."""
    from pathlib import Path

    rel = (data.get("audioPath") or "").strip()
    if not rel:
        return None
    audio = (Path(json_path).parent / rel).resolve()
    if not audio.is_file():
        print(f"[org_export] Audio listed but not found: {audio}")
        return None
    # Cloudflare and Supabase both have limits, and a multi-hour recording is
    # not worth failing the whole export over. The transcript still goes.
    if audio.stat().st_size > 200 * 1024 * 1024:
        print(f"[org_export] Audio too large ({audio.stat().st_size // 1048576} MB) — skipping the file.")
        return None
    return audio


def _upload_audio(audio, url: str) -> None:
    """PUT the recording. Never raises — the transcript is already safe."""
    try:
        with open(audio, "rb") as f:
            req = urllib.request.Request(
                url,
                data=f.read(),
                headers={"content-type": "application/octet-stream"},
                method="PUT",
            )
            with urllib.request.urlopen(req, timeout=300) as res:
                if 200 <= res.status < 300:
                    print(f"[org_export] Audio uploaded ({audio.stat().st_size // 1048576} MB).")
                else:
                    print(f"[org_export] Audio upload returned {res.status}.")
    except Exception as e:
        print(f"[org_export] Audio upload skipped ({e}).")


def export_to_org(json_path: str) -> bool:
    """Returns True if Simple Org accepted it. Never raises."""
    try:
        token = _token()
        if not token:
            print("[org_export] No Simple Org token configured — skipping.")
            return False

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        met_at = _met_at(data)
        if not met_at:
            print("[org_export] Transcription has no date — skipping.")
            return False

        # The full text, flattened. Speaker labels are kept: who said a thing is
        # usually the point of going back to a transcript.
        lines = []
        for entry in data.get("transcribedText") or []:
            speaker = (entry.get("speaker") or "").strip()
            text = (entry.get("text") or "").strip()
            if text:
                lines.append(f"{speaker}: {text}" if speaker else text)

        payload = {
            "title": data.get("title") or "Namnlöst möte",
            "met_at": met_at,
            "speakers": data.get("speakers") or [],
            "summary": (data.get("summary") or "").strip() or None,
            "decisions": [d for d in (data.get("decisions") or []) if str(d).strip()],
            "action_items": [a for a in (data.get("actionItems") or []) if str(a).strip()],
            "transcript": "\n".join(lines) or None,
        }

        # The recording, if there is one. The transcript is a machine's
        # reading of it; the audio is what settles a dispute about what was
        # actually said, so it travels with the text rather than staying on
        # one laptop.
        audio = _audio_path(json_path, data)
        if audio:
            payload["audio_name"] = audio.name

        req = urllib.request.Request(
            ENDPOINT,
            data=json.dumps(payload).encode("utf-8"),
            headers={"content-type": "application/json", "x-transcribe-token": token},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as res:
            ok = 200 <= res.status < 300
            answer = json.loads(res.read().decode("utf-8") or "{}")

        print(f"[org_export] {'Sent' if ok else 'Rejected'}: {payload['title']}")

        # Straight to storage on the one-shot URL the server handed back — the
        # file never passes through the Worker.
        if ok and audio and answer.get("upload"):
            _upload_audio(audio, answer["upload"])

        return ok

    except urllib.error.HTTPError as e:
        # Print the body — "not_configured" and "unauthorized" need completely
        # different responses, and a bare status code hides which it is.
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")[:200]
        except Exception:
            pass
        print(f"[org_export] HTTP {e.code}: {body}")
        return False
    except Exception as e:
        print(f"[org_export] Skipped ({e}).")
        return False
