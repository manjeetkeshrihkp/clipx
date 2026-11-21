#!/usr/bin/env python3
"""GitHub Actions Autonomous Auto-Pilot Runner for ClipX.

Runs headless inside a GitHub Actions runner or scheduled cron job:
1. Researches trending viral videos (YouTube/channels/niche).
2. Transcribes & scouts viral clips using AI (Groq / Gemini / OpenAI).
3. Renders 9:16 vertical shorts with animated subtitles.
4. Distributes to Instagram Business accounts (if tokens are configured).
5. Exports generated MP4 clips to an output directory for GitHub artifact download.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import sys
import time
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("clipx.actions")


def main() -> int:
    print("=" * 60)
    print("🚀 ClipX Headless Auto-Pilot (GitHub Actions Cloud Runner)")
    print("=" * 60)

    # 1. Ensure required directories
    workspace = Path(__file__).resolve().parent.parent
    os.chdir(workspace)
    sys.path.insert(0, str(workspace))

    from studio import accounts, auth, autotrend, config, ctx, jobs

    output_dir = Path(os.environ.get("OUTPUT_DIR", "output_clips"))
    output_dir.mkdir(parents=True, exist_ok=True)

    # 2. Setup user context
    uid = "local"
    try:
        user = auth.local_user()
        if user and user.id:
            uid = user.id
    except Exception:
        pass

    with ctx.as_user(uid):
        # 3. Setup Instagram accounts from environment secrets if provided
        ig_tokens_raw = (
            os.environ.get("INSTAGRAM_ACCESS_TOKENS")
            or os.environ.get("INSTAGRAM_ACCESS_TOKEN")
            or ""
        ).strip()

        connected_ig = []
        if ig_tokens_raw:
            tokens = [t.strip() for t in ig_tokens_raw.split(",") if t.strip()]
            for idx, tok in enumerate(tokens):
                try:
                    logger.info(f"Connecting Instagram account #{idx + 1}...")
                    acc = accounts.instagram_add(tok)
                    connected_ig.append(acc["id"])
                    logger.info(f"Connected Instagram account: {acc.get('name')} (ID: {acc.get('id')})")
                except Exception as e:
                    logger.warning(f"Could not connect token #{idx + 1}: {e}")

        existing = [a["id"] for a in accounts.list_accounts() if a.get("platform") == "instagram"]
        all_ig = list(set(connected_ig + existing))
        logger.info(f"Active Instagram accounts for distribution: {len(all_ig)}")

        # 4. Configure Auto-Pilot settings from Environment Variables
        niche = os.environ.get("AUTOTREND_NICHE", "podcast")
        query = os.environ.get("AUTOTREND_QUERY", "")
        channels_raw = os.environ.get("AUTOTREND_CHANNELS", "")
        channels = [c.strip() for c in channels_raw.split(",") if c.strip()]
        max_clips = int(os.environ.get("AUTOTREND_MAX_CLIPS", "2"))
        min_score = int(os.environ.get("AUTOTREND_MIN_SCORE", "70"))
        style = os.environ.get("AUTOTREND_STYLE", "bounce")
        layout = os.environ.get("AUTOTREND_LAYOUT", "blur")

        settings_patch = {
            "enabled": True,
            "niche": niche,
            "custom_query": query,
            "channels": channels,
            "max_clips": max_clips,
            "min_score": min_score,
            "style": style,
            "layout": layout,
            "target_accounts": all_ig,
            "post_mode": "now" if os.environ.get("AUTOTREND_POST_NOW", "1") == "1" else "queue",
        }
        autotrend.save_settings(settings_patch)
        logger.info(f"Auto-Pilot Settings: Niche='{niche}', MaxClips={max_clips}, Style='{style}', Layout='{layout}'")

        # 5. Start ClipX background job processing engine
        logger.info("Initializing ClipX worker threads and pipeline...")
        jobs.start()

        # 6. Execute one autonomous research & clip cycle
        logger.info("Scouting trending viral content...")
        run_res = autotrend.run_cycle(manual=True)
        status = run_res.get("status")

        if status == "no_candidate":
            logger.info(f"Cycle completed: {run_res.get('message')}")
            return 0

        if status != "queued":
            logger.warning(f"Unexpected status: {run_res}")
            return 0

        job_id = run_res.get("job_id")
        video_title = run_res.get("title")
        video_url = run_res.get("url")
        logger.info(f"Successfully selected trending video: '{video_title}'")
        logger.info(f"Source URL: {video_url}")
        logger.info(f"Job ID: {job_id}. Processing video (download -> audio -> transcript -> AI picks -> video render)...")

        # 7. Monitor job execution until complete
        last_stage = ""
        last_progress = -1.0
        start_t = time.time()
        timeout_seconds = int(os.environ.get("JOB_TIMEOUT_SEC", "1800"))  # 30 min max

        while time.time() - start_t < timeout_seconds:
            time.sleep(5)
            job = jobs.get(job_id)
            if not job:
                continue

            cur_status = job.get("status")
            cur_stage = job.get("stage", "")
            cur_progress = job.get("progress", 0.0)

            if cur_stage != last_stage or abs(cur_progress - last_progress) >= 0.05:
                pct = int(cur_progress * 100) if isinstance(cur_progress, (int, float)) else 0
                logger.info(f"Progress [{pct}%]: {cur_stage}")
                last_stage = cur_stage
                last_progress = cur_progress

            if cur_status in ("done", "error"):
                break

        # 8. Report results and export clips
        job = jobs.get(job_id)
        if not job or job.get("status") != "done":
            err = job.get("error") if job else "Timed out"
            logger.error(f"Job failed or did not finish: {err}")
            return 1

        clips = job.get("clips", [])
        logger.info("=" * 60)
        logger.info(f"🎉 Job Completed! Generated {len(clips)} clip(s) for '{video_title}'")
        logger.info("=" * 60)

        job_dir = Path(job["dir"])
        exported_count = 0

        for clip in clips:
            cid = clip.get("id")
            score = clip.get("score", 0)
            hook = clip.get("hook", "")
            dur = round(clip.get("end", 0) - clip.get("start", 0), 1)
            clip_status = clip.get("status")
            src_file = job_dir / f"{cid}.mp4"

            logger.info(f"• Clip [{cid}]: {dur}s | Score: {score}/100 | Hook: '{hook}' | Status: {clip_status}")

            if src_file.exists() and clip_status == "done":
                # Clean filename for export
                safe_name = f"{job_id}_{cid}_{int(score)}pts.mp4"
                dest_file = output_dir / safe_name
                shutil.copy2(src_file, dest_file)
                logger.info(f"  -> Exported artifact: {dest_file}")
                exported_count += 1

                # If Instagram posting is enabled and accounts are linked
                if all_ig and score >= min_score:
                    for aid in all_ig:
                        acc = accounts.get(aid)
                        if not acc:
                            continue
                        logger.info(f"  -> Uploading to Instagram account {acc.get('name')}...")
                        try:
                            caption = f"{hook}\n\n{clip.get('description', '')}\n\n#reels #viral #trending #shorts"
                            remote_id, permalink = accounts.instagram_upload(acc, dest_file, caption, job_id=job_id)
                            logger.info(f"  ✅ Posted to Instagram! Remote ID: {remote_id} | Link: {permalink or 'Processing'}")
                        except Exception as e:
                            logger.error(f"  ❌ Instagram upload failed for {acc.get('name')}: {e}")

        # Write summary manifest
        manifest = {
            "timestamp": time.time(),
            "job_id": job_id,
            "title": video_title,
            "url": video_url,
            "clips_count": len(clips),
            "exported_count": exported_count,
            "clips": [
                {
                    "id": c.get("id"),
                    "score": c.get("score"),
                    "hook": c.get("hook"),
                    "start": c.get("start"),
                    "end": c.get("end"),
                    "status": c.get("status"),
                }
                for c in clips
            ],
        }
        (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        logger.info(f"Run manifest saved to {output_dir / 'run_manifest.json'}")
        print("=" * 60)
        print(f"✨ Finished successfully! {exported_count} clips ready in {output_dir}")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    sys.exit(main())
