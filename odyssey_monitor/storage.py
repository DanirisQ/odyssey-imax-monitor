from __future__ import annotations

import csv
from dataclasses import asdict
import json
from pathlib import Path
from typing import Iterable

from .models import Showtime


STATE_VERSION = 1
HISTORY_COLUMNS = [
    "show_key",
    "movie",
    "show_date",
    "start_time",
    "hall",
    "version",
    "language",
    "source_id",
    "source",
    "first_seen_at",
]


def load_state(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {"version": STATE_VERSION, "initialized": False, "seen": {}}
    with p.open("r", encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("version", STATE_VERSION)
    data.setdefault("initialized", True)
    data.setdefault("seen", {})
    return data


def save_state(path: str, state: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    tmp.replace(p)


def append_history(path: str, showtimes: Iterable[Showtime], first_seen_at: str) -> None:
    items = list(showtimes)
    if not items:
        return
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    exists = p.exists() and p.stat().st_size > 0
    with p.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=HISTORY_COLUMNS)
        if not exists:
            writer.writeheader()
        for s in items:
            row = {
                "show_key": s.key,
                **s.to_dict(),
                "first_seen_at": first_seen_at,
            }
            writer.writerow(row)
