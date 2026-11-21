"""Autonomous Hourly Trend Researcher & Instagram Multi-Account Publisher for ClipX.

Researches trending videos (YouTube trending, viral niches, podcasts, gaming, tech),
filters candidates, automatically triggers transcription, AI highlight scouting,
9:16 vertical rendering, and schedules distribution across connected Instagram Business accounts.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

from . import accounts, auth, config, ctx, jobs, posting

logger = logging.getLogger("clipx.autotrend")

_lock = threading.RLock()
CONFIG_FILE = config.DATA_DIR / "autotrend.json"
HISTORY_FILE = config.DATA_DIR / "autotrend_history.json"

DEFAULTS = {
    "enabled": False,
    "interval_hours": 1.0,
    "niche": "podcast",          # podcast | tech | gaming | motivation | finance | custom | channels
    "custom_query": "trending podcast viral discussion",
    "channels": [],              # specific YouTube channel URLs to track
    "min_duration_min": 5,
    "max_duration_min": 60,
    "max_clips": 3,
    "min_score": 75,
    "style": "bounce",           # bounce | hype | clean
    "layout": "blur",            # blur | crop | gameplay | zoom
    "target_accounts": [],       # list of IG account IDs or empty for all connected IG accounts
    "post_mode": "queue",        # queue (smooth spaced posting) | now (immediate post)
    "last_run": 0.0,
    "next_run": 0.0,
    "status_message": "Auto-Pilot is ready.",
}

NICHE_QUERIES = {
    "podcast": "ytsearch12:trending podcast interview full",
    "tech": "ytsearch12:viral tech ai news breakdown today",
    "gaming": "ytsearch12:viral gaming moments twitch highlights",
    "motivation": "ytsearch12:motivational speech business podcast",
    "finance": "ytsearch12:finance investing economy discussion podcast",
}


def get_settings() -> dict[str, Any]:
    with _lock:
        if not CONFIG_FILE.exists():
            return dict(DEFAULTS)
        try:
            saved = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            return {**DEFAULTS, **saved}
        except (ValueError, OSError):
            return dict(DEFAULTS)


def save_settings(data: dict[str, Any]) -> dict[str, Any]:
    with _lock:
        current = get_settings()
        updated = {**current, **data}
        if updated.get("interval_hours", 1.0) < 0.25:
            updated["interval_hours"] = 0.25
        CONFIG_FILE.write_text(json.dumps(updated, indent=2), encoding="utf-8")
        return updated


def get_history() -> dict[str, Any]:
    with _lock:
        if not HISTORY_FILE.exists():
            return {"processed_urls": [], "runs": []}
        try:
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return {"processed_urls": [], "runs": []}


def record_run(entry: dict[str, Any]):
    with _lock:
        hist = get_history()
        hist.setdefault("runs", []).insert(0, entry)
        hist["runs"] = hist["runs"][:50]  # keep last 50 runs
        if entry.get("url") and entry["url"] not in hist.setdefault("processed_urls", []):
            hist["processed_urls"].append(entry["url"])
            if len(hist["processed_urls"]) > 500:
                hist["processed_urls"] = hist["processed_urls"][-500:]
        HISTORY_FILE.write_text(json.dumps(hist, indent=2), encoding="utf-8")


def discover_candidate(settings: dict[str, Any]) -> dict[str, Any] | None:
    """Scrapes YouTube search / channel feeds with yt-dlp to find the freshest viral video."""
    import yt_dlp

    history = get_history()
    seen_urls = set(history.get("processed_urls", []))

    niche = settings.get("niche", "podcast")
    custom_query = (settings.get("custom_query") or "").strip()
    channels = settings.get("channels") or []

    query = ""
    if niche == "channels" and channels:
        # Check first configured channel
        ch = str(channels[0]).strip().rstrip("/")
        query = ch + "/videos" if not ch.endswith("/videos") else ch
    elif niche == "custom" and custom_query:
        query = f"ytsearch12:{custom_query}"
    else:
        query = NICHE_QUERIES.get(niche, NICHE_QUERIES["podcast"])

    ydl_opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(query, download=False)
            entries = info.get("entries", []) if info else []
    except Exception as e:
        logger.error(f"Error querying trends: {e}")
        return None

    min_sec = settings.get("min_duration_min", 5) * 60
    max_sec = settings.get("max_duration_min", 60) * 60

    for entry in entries:
        if not entry:
            continue
        url = entry.get("url") or entry.get("webpage_url") or ""
        if not url.startswith("http"):
            url = f"https://www.youtube.com/watch?v={entry.get('id')}" if entry.get("id") else ""
        if not url or url in seen_urls:
            continue

        dur = float(entry.get("duration") or 0)
        # If duration is 0, yt-dlp flat extract might not have duration; check or allow
        if dur > 0 and (dur < min_sec or dur > max_sec):
            continue

        title = entry.get("title") or "Trending Video"
        return {
            "url": url,
            "title": title,
            "duration": dur,
            "uploader": entry.get("uploader") or entry.get("channel") or "",
        }

    return None


def run_cycle(manual: bool = False) -> dict[str, Any]:
    """Executes one research-and-clip cycle."""
    settings = get_settings()
    if not settings.get("enabled") and not manual:
        return {"status": "skipped", "message": "Auto-Pilot is currently disabled."}

    # Find candidate
    save_settings({"status_message": "Researching trending content..."})
    candidate = discover_candidate(settings)
    if not candidate:
        msg = "No suitable new trending video found in this pass (all checked or outside duration range)."
        save_settings({"status_message": msg, "last_run": time.time(),
                       "next_run": time.time() + settings.get("interval_hours", 1.0) * 3600})
        record_run({"timestamp": time.time(), "status": "no_candidate", "message": msg})
        return {"status": "no_candidate", "message": msg}

    url = candidate["url"]
    title = candidate["title"]
    save_settings({"status_message": f"Processing trending video: {title[:50]}..."})

    # Prepare job options
    opts = {
        "max_clips": settings.get("max_clips", 3),
        "min_len": 15,
        "max_len": 60,
        "style": settings.get("style", "bounce"),
        "layout": settings.get("layout", "blur"),
        "captions": True,
        "quality": "1080",
    }

    # Context user
    uid = "local"
    try:
        user = auth.local_user()
        if user and user.id:
            uid = user.id
    except Exception:
        pass

    with ctx.as_user(uid):
        # Determine target Instagram accounts
        available_ig = [
            a["id"] for a in accounts.list_accounts() if a.get("platform") == "instagram"
        ]
        target_ig = settings.get("target_accounts") or available_ig
        valid_targets = [a for a in target_ig if a in available_ig]

        # Create ClipX Job
        job = jobs.create(
            source={"type": "url", "url": url, "name": title},
            options=opts,
            enqueue=True,
        )

        job_id = job["id"]
        job["autotrend"] = True
        job["autotrend_targets"] = valid_targets
        job["autotrend_post_mode"] = settings.get("post_mode", "queue")
        job["autotrend_min_score"] = settings.get("min_score", 75)
        jobs.save(job)

    now = time.time()
    next_time = now + settings.get("interval_hours", 1.0) * 3600
    save_settings({
        "last_run": now,
        "next_run": next_time,
        "status_message": f"Queued job for '{title[:45]}...'. Clips will distribute to {len(valid_targets)} Instagram page(s).",
    })

    run_info = {
        "timestamp": now,
        "url": url,
        "title": title,
        "job_id": job_id,
        "target_accounts": valid_targets,
        "status": "queued",
        "message": f"Created job {job_id} for '{title}'",
    }
    record_run(run_info)
    return run_info


def on_autotrend_clip_ready(job: dict[str, Any], clip: dict[str, Any]):
    """Called by the pipeline when a clip finishes rendering for an auto-trend job."""
    if not job.get("autotrend"):
        return

    min_score = job.get("autotrend_min_score", 75)
    score = clip.get("score", 0)
    if score < min_score:
        logger.info(f"Auto-trend clip {clip.get('id')} score {score} < {min_score}, skipping auto-post.")
        return

    target_accounts = job.get("autotrend_targets") or []
    if not target_accounts:
        return

    post_now = job.get("autotrend_post_mode") == "now"
    with ctx.as_user(job["user"]):
        posting.enqueue(job, clip, target_accounts, now=post_now)
        logger.info(f"Auto-trend clip {clip.get('id')} queued for {len(target_accounts)} Instagram account(s).")


# ---------------------------------------------------------------- Background Worker
_worker_started = False


def _loop():
    logger.info("ClipX Auto-Trend background scheduler started.")
    while True:
        try:
            settings = get_settings()
            if settings.get("enabled"):
                now = time.time()
                next_run = settings.get("next_run", 0.0)
                if now >= next_run:
                    run_cycle(manual=False)
        except Exception as e:
            logger.error(f"Error in autotrend loop: {e}")
        time.sleep(30)


def start():
    global _worker_started
    with _lock:
        if _worker_started:
            return
        _worker_started = True
        t = threading.Thread(target=_loop, name="clipx-autotrend", daemon=True)
        t.start()
