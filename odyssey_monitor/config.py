from __future__ import annotations

from dataclasses import dataclass
import os
from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return int(raw)


def _csv(name: str, fallback: str) -> tuple[str, ...]:
    raw = os.getenv(name, fallback)
    return tuple(x.strip() for x in raw.split(",") if x.strip())


@dataclass(frozen=True, slots=True)
class Config:
    cinema_id: int = _int("CINEMA_ID", 37534)
    city_id: int = _int("CITY_ID", 10)
    cinema_name: str = os.getenv("CINEMA_NAME", "MOViE MOViE影城（前滩太古里店）")
    target_movie: str = os.getenv("TARGET_MOVIE", "奥德赛")
    target_movie_aliases: tuple[str, ...] = _csv("TARGET_MOVIE_ALIASES", "奥德赛,The Odyssey")
    format_keyword: str = os.getenv("TARGET_FORMAT_KEYWORD", "IMAX")
    timezone: str = os.getenv("TIMEZONE", "Asia/Shanghai")
    maoyan_cookie: str = os.getenv("MAOYAN_COOKIE", "").strip()

    smtp_host: str = os.getenv("SMTP_HOST", "").strip()
    smtp_port: int = _int("SMTP_PORT", 465)
    smtp_user: str = os.getenv("SMTP_USER", "").strip()
    smtp_password: str = os.getenv("SMTP_PASSWORD", "").strip()
    email_from: str = os.getenv("EMAIL_FROM", "").strip()
    email_to: tuple[str, ...] = _csv("EMAIL_TO", "")
    smtp_use_ssl: bool = _bool("SMTP_USE_SSL", True)
    smtp_starttls: bool = _bool("SMTP_STARTTLS", False)

    notify_on_first_run: bool = _bool("NOTIFY_ON_FIRST_RUN", False)
    state_path: str = os.getenv("STATE_PATH", "data/state.json")
    history_path: str = os.getenv("HISTORY_PATH", "data/history.csv")

    @property
    def cinema_url(self) -> str:
        return f"https://www.maoyan.com/cinema/{self.cinema_id}"

    @property
    def email_ready(self) -> bool:
        return bool(
            self.smtp_host
            and self.smtp_user
            and self.smtp_password
            and self.email_from
            and self.email_to
        )
