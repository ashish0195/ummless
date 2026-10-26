"""Print the pilot metrics from the spec as JSON, read from the database in DATABASE_URL.

Usage (from backend/):
    python scripts/pilot_metrics.py                                   # everyone
    python scripts/pilot_metrics.py --since 2026-11-01 --until 2026-12-01   # people who joined in November
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from app.config import get_settings  # noqa: E402
from app.db import Base, make_engine, make_session_factory  # noqa: E402
from app.services import pilot_metrics  # noqa: E402


def _day(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=UTC)


def main() -> None:
    parser = argparse.ArgumentParser(description="Comlogue pilot metrics: engagement and learning, reported apart.")
    parser.add_argument("--since", type=_day, help="Only people who joined on or after this UTC date (YYYY-MM-DD)")
    parser.add_argument("--until", type=_day, help="Only people who joined before this UTC date (YYYY-MM-DD)")
    args = parser.parse_args()
    engine = make_engine(get_settings().database_url)
    Base.metadata.create_all(engine)  # same as server startup; a fresh database just reports zeros
    with make_session_factory(engine)() as db:
        print(json.dumps(pilot_metrics.compute(db, args.since, args.until), indent=2))


if __name__ == "__main__":
    main()
