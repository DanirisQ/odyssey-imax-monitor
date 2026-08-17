from __future__ import annotations

from datetime import datetime
import logging
from zoneinfo import ZoneInfo

from .config import Config
from .maoyan import MaoyanClient
from .notifier import send_new_showtimes
from .storage import append_history, load_state, save_state

LOG = logging.getLogger(__name__)


def now_iso(tz_name: str) -> str:
    return datetime.now(ZoneInfo(tz_name)).isoformat(timespec="seconds")


def run() -> int:
    cfg = Config()
    detected_at = now_iso(cfg.timezone)
    state = load_state(cfg.state_path)

    current = MaoyanClient(cfg).get_target_imax_showtimes()
    LOG.info("Current target IMAX screenings: %d", len(current))
    if not current:
        LOG.warning("No target IMAX screenings found. State was not changed.")
        return 0

    seen = state.setdefault("seen", {})
    is_first_run = not bool(state.get("initialized"))
    new_items = [s for s in current if s.key not in seen]

    if new_items:
        LOG.info("Discovered %d never-seen screenings", len(new_items))
        for s in new_items:
            seen[s.key] = {
                **s.to_dict(),
                "first_seen_at": detected_at,
                "notified_at": None,
            }
        append_history(cfg.history_path, new_items, detected_at)

    state["initialized"] = True
    state["last_successful_check_at"] = detected_at
    state["last_visible_count"] = len(current)

    # First-run baseline: mark current sessions as intentionally suppressed.
    if is_first_run and not cfg.notify_on_first_run:
        for s in new_items:
            seen[s.key]["notified_at"] = "baseline"
        save_state(cfg.state_path, state)
        LOG.info("Baseline created. Existing screenings were not emailed.")
        return 0

    # Retry any discovered-but-not-yet-notified sessions, not only this run's additions.
    pending_keys = [k for k, v in seen.items() if v.get("notified_at") in (None, "")]
    pending = []
    for key in pending_keys:
        raw = seen[key]
        # Only notify sessions that still look like the target movie / format record.
        from .models import Showtime
        pending.append(Showtime(
            movie=raw.get("movie", cfg.target_movie),
            show_date=raw.get("show_date", ""),
            start_time=raw.get("start_time", ""),
            hall=raw.get("hall", ""),
            version=raw.get("version", ""),
            language=raw.get("language", ""),
            source_id=raw.get("source_id", ""),
            source=raw.get("source", "maoyan"),
        ))

    # Persist discovery before attempting SMTP so a send failure doesn't lose first-seen time.
    save_state(cfg.state_path, state)

    if pending:
        send_new_showtimes(pending, detected_at, cfg)
        notified_at = now_iso(cfg.timezone)
        for key in pending_keys:
            seen[key]["notified_at"] = notified_at
        save_state(cfg.state_path, state)
        LOG.info("Email sent for %d screenings", len(pending))
    else:
        LOG.info("No new screenings to notify")

    return 0


def cli() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    raise SystemExit(run())


if __name__ == "__main__":
    cli()
