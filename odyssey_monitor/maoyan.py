from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
import json
import logging
import re
from typing import Any, Iterable

import requests
from bs4 import BeautifulSoup

from .config import Config
from .models import Showtime

LOG = logging.getLogger(__name__)

_MOBILE_SHOWS_URL = "https://m.maoyan.com/mtrade/cinema/cinema/shows.json"
_DATE_RE = re.compile(r"^\d{4}-\d{1,2}-\d{1,2}$")
_TIME_RE = re.compile(r"^(?:[01]?\d|2[0-3]):[0-5]\d$")

DATE_KEYS = ("showDate", "show_date", "date", "dt", "day")
TIME_KEYS = ("showTime", "show_time", "startTime", "start_time", "tm", "time")
HALL_KEYS = ("hallName", "hall_name", "hall", "th", "roomName", "room_name")
VERSION_KEYS = ("version", "showType", "show_type", "tp", "dim", "format")
LANG_KEYS = ("language", "lang", "lng")
ID_KEYS = ("seqNo", "seq_no", "showId", "show_id", "id")
MOVIE_KEYS = ("movieName", "movie_name", "nm", "filmName", "film_name", "title")


def _clean(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()


def _first(obj: dict, keys: Iterable[str]) -> str:
    for key in keys:
        if key in obj and obj[key] not in (None, ""):
            return _clean(obj[key])
    return ""


def _normalize_date(value: str) -> str:
    value = _clean(value)
    if not value:
        return ""
    # Full datetime, e.g. 2026-08-18 09:45:00 / ISO form.
    if len(value) >= 10 and _DATE_RE.match(value[:10]):
        return datetime.strptime(value[:10], "%Y-%m-%d").date().isoformat()
    if _DATE_RE.match(value):
        return datetime.strptime(value, "%Y-%m-%d").date().isoformat()
    return ""


def _normalize_time(value: str) -> str:
    value = _clean(value)
    if not value:
        return ""
    # Full datetime.
    match = re.search(r"(?:T|\s)(\d{1,2}:\d{2})(?::\d{2})?", value)
    if match:
        value = match.group(1)
    # Sometimes time is '9:45'.
    if re.match(r"^\d{1,2}:\d{2}$", value):
        hh, mm = value.split(":")
        value = f"{int(hh):02d}:{mm}"
    return value if _TIME_RE.match(value) else ""


def _movie_matches(value: str, aliases: tuple[str, ...]) -> bool:
    v = _clean(value).casefold()
    if not v:
        return False
    return any(a.casefold() in v or v in a.casefold() for a in aliases if a)


def _looks_imax(hall: str, version: str, keyword: str) -> bool:
    needle = keyword.casefold()
    return needle in hall.casefold() or needle in version.casefold()


def extract_showtimes_from_json(payload: Any, cfg: Config) -> list[Showtime]:
    """Schema-tolerant extraction from Maoyan's mobile cinema JSON.

    Maoyan has changed nesting/field names over time. We walk the target movie
    subtree and inherit parent-level date/movie metadata, which handles common
    shapes such as showDate -> plist[] where individual rows only carry `tm`.
    """
    found: dict[str, Showtime] = {}

    def walk(
        node: Any,
        inherited_movie: str = "",
        inherited_date: str = "",
        in_target_movie: bool = False,
    ) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item, inherited_movie, inherited_date, in_target_movie)
            return
        if not isinstance(node, dict):
            return

        movie_here = _first(node, MOVIE_KEYS)
        if not movie_here and "name" in node and any(
            k in node for k in ("movieId", "movie_id", "filmId", "film_id", "shows", "showList")
        ):
            movie_here = _clean(node.get("name"))
        movie_name = movie_here or inherited_movie
        target_here = in_target_movie or _movie_matches(movie_here, cfg.target_movie_aliases)

        date_here = _normalize_date(_first(node, DATE_KEYS)) or inherited_date
        time_here = _normalize_time(_first(node, TIME_KEYS))
        # A datetime may be stored entirely inside a time-like field.
        if not date_here:
            raw_time = _first(node, TIME_KEYS)
            date_here = _normalize_date(raw_time)

        hall = _first(node, HALL_KEYS)
        version = _first(node, VERSION_KEYS)
        language = _first(node, LANG_KEYS)
        source_id = _first(node, ID_KEYS)

        if target_here and date_here and time_here and (hall or version):
            if _looks_imax(hall, version, cfg.format_keyword):
                item = Showtime(
                    movie=movie_name or cfg.target_movie,
                    show_date=date_here,
                    start_time=time_here,
                    hall=hall,
                    version=version,
                    language=language,
                    source_id=source_id,
                    source="maoyan-mobile-json",
                )
                found[item.key] = item

        # If a node itself clearly names another movie, don't leak a previous
        # target-movie context into that sibling subtree.
        if movie_here and not _movie_matches(movie_here, cfg.target_movie_aliases):
            next_target = False
        else:
            next_target = target_here

        for value in node.values():
            if isinstance(value, (dict, list)):
                walk(value, movie_name, date_here, next_target)

    walk(payload)
    return sorted(found.values(), key=lambda x: (x.show_date, x.start_time, x.hall, x.version))


def _extract_date_from_element(el) -> str:
    cur = el
    for _ in range(5):
        if cur is None:
            break
        attrs = getattr(cur, "attrs", {}) or {}
        for key in ("data-date", "data-show-date", "date"):
            if key in attrs:
                d = _normalize_date(attrs.get(key, ""))
                if d:
                    return d
        cur = getattr(cur, "parent", None)
    return ""


def extract_showtimes_from_html(html: str, cfg: Config) -> list[Showtime]:
    soup = BeautifulSoup(html, "html.parser")
    found: dict[str, Showtime] = {}

    panels = soup.select("div.show-list")
    for panel in panels:
        name_el = panel.select_one("h3.movie-name, .movie-name")
        movie_name = _clean(name_el.get_text(" ", strip=True) if name_el else "")
        if not _movie_matches(movie_name, cfg.target_movie_aliases):
            continue

        # Maoyan's desktop cinema page historically uses these classes.
        date_nodes = panel.select(".show-date [data-date], .date-item[data-date], [data-show-date]")
        dates: list[str] = []
        for node in date_nodes:
            d = _normalize_date(node.get("data-date") or node.get("data-show-date") or "")
            if d and d not in dates:
                dates.append(d)

        tables = panel.select("table.plist")
        for idx, table in enumerate(tables):
            table_date = _extract_date_from_element(table)
            if not table_date and len(tables) == len(dates) and idx < len(dates):
                table_date = dates[idx]
            if not table_date:
                # Active date is a useful fallback if the page only renders one table.
                active_date = panel.select_one(".show-date .active[data-date], .date-item.active[data-date]")
                if active_date:
                    table_date = _normalize_date(active_date.get("data-date", ""))
            if not table_date:
                continue

            for row in table.select("tr"):
                begin = row.select_one(".begin-time")
                hall_el = row.select_one(".hall")
                lang_el = row.select_one(".lang")
                version_el = row.select_one(".version, .show-type, .tp")
                start_time = _normalize_time(begin.get_text(" ", strip=True) if begin else "")
                hall = _clean(hall_el.get_text(" ", strip=True) if hall_el else "")
                language = _clean(lang_el.get_text(" ", strip=True) if lang_el else "")
                version = _clean(version_el.get_text(" ", strip=True) if version_el else "")
                # On Maoyan, `.lang` often contains combined language/version text.
                combined_version = " ".join(x for x in (language, version) if x)
                if not start_time or not _looks_imax(hall, combined_version, cfg.format_keyword):
                    continue
                source_id = row.get("data-seq-no") or row.get("data-show-id") or ""
                item = Showtime(
                    movie=movie_name or cfg.target_movie,
                    show_date=table_date,
                    start_time=start_time,
                    hall=hall,
                    version=combined_version,
                    language=language,
                    source_id=_clean(source_id),
                    source="maoyan-desktop-html",
                )
                found[item.key] = item

    return sorted(found.values(), key=lambda x: (x.show_date, x.start_time, x.hall, x.version))


class MaoyanClient:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 "
                "Mobile/15E148 Safari/604.1"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
            "Referer": f"https://m.maoyan.com/shows/{cfg.cinema_id}",
        })
        if cfg.maoyan_cookie:
            self.session.headers["Cookie"] = cfg.maoyan_cookie

    def _fetch_mobile_json(self) -> Any:
        params = {
            "ci": self.cfg.city_id,
            "cinemaId": self.cfg.cinema_id,
            "channelId": 4,
            "optimus_risk_level": 71,
            "optimus_code": 10,
        }
        r = self.session.get(_MOBILE_SHOWS_URL, params=params, timeout=20)
        r.raise_for_status()
        if "json" not in r.headers.get("content-type", "").lower() and not r.text.lstrip().startswith(("{", "[")):
            raise ValueError(f"Mobile endpoint did not return JSON (content-type={r.headers.get('content-type')})")
        return r.json()

    def _fetch_desktop_html(self) -> str:
        headers = dict(self.session.headers)
        headers["User-Agent"] = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0 Safari/537.36"
        )
        headers["Referer"] = "https://www.maoyan.com/"
        r = self.session.get(self.cfg.cinema_url, headers=headers, timeout=20)
        r.raise_for_status()
        return r.text

    def get_target_imax_showtimes(self) -> list[Showtime]:
        errors: list[str] = []
        try:
            payload = self._fetch_mobile_json()
            items = extract_showtimes_from_json(payload, self.cfg)
            if items:
                LOG.info("Mobile JSON: found %d target IMAX screenings", len(items))
                return items
            errors.append("mobile JSON returned no matching screenings")
        except Exception as exc:  # keep fallback alive
            errors.append(f"mobile JSON failed: {exc}")
            LOG.warning(errors[-1])

        try:
            html = self._fetch_desktop_html()
            items = extract_showtimes_from_html(html, self.cfg)
            if items:
                LOG.info("Desktop HTML: found %d target IMAX screenings", len(items))
                return items
            errors.append("desktop HTML returned no matching screenings")
        except Exception as exc:
            errors.append(f"desktop HTML failed: {exc}")
            LOG.warning(errors[-1])

        raise RuntimeError("; ".join(errors))
