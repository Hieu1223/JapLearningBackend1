"""Backfill merged Sudachi tokens for existing transcripts.

Standalone (not part of the app). Connects to the database, finds
already-transcribed rows (status = Finish) whose stored ``data`` does not yet
have a ``tokens`` field, and adds the Sudachi-merged tokens using the same
logic/setting as the live pipeline (app.tokenization.tokenize.merge_transcript_tokens).

Run:
    python scripts/backfill_transcript_tokens.py
    DATABASE_URL=postgresql://... python scripts/backfill_transcript_tokens.py

Only Finished transcripts are touched; rows already containing ``tokens`` are
skipped, so the script is safe to re-run.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")

try:
    import psycopg2
except ImportError:
    sys.exit("psycopg2 is required (pip install psycopg2)")

# Reuse the exact same merge logic / Sudachi setting as the app.
from app.tokenization.tokenize import merge_transcript_tokens  # noqa: E402


def main() -> None:
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set (set it in .env or the environment).")

    conn = psycopg2.connect(url)
    try:
        conn.autocommit = False
        cur = conn.cursor()

        # Only transcripts that are Finished and have data.
        cur.execute(
            """
            SELECT id, data
            FROM public.transcript
            WHERE status = 3
              AND data IS NOT NULL
            ORDER BY date_created
            """
        )
        rows = cur.fetchall()
        print(f"[backfill] {len(rows)} transcript(s) to process.")

        updated = 0
        for tid, data in rows:
            data = json.loads(data)
            segments = data.get("segments", [])
            merged = merge_transcript_tokens(segments)
            changed = False
            for seg, seg_words in zip(segments, merged):
                if seg.get("words") != seg_words:
                    seg["words"] = seg_words
                    changed = True

            if not changed:
                continue

            cur.execute(
                "UPDATE public.transcript SET data = %s WHERE id = %s",
                (json.dumps(data), tid),
            )
            total = sum(len(s) for s in merged)
            updated += 1
            print(f"[backfill] updated {tid} ({total} merged tokens)")

        conn.commit()
        print(f"[backfill] done. {updated} transcript(s) updated.")
    except Exception as e:  # noqa: BLE001
        conn.rollback()
        print(f"[backfill] FAILED, rolled back: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
