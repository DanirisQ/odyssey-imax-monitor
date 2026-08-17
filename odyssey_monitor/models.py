from __future__ import annotations

from dataclasses import asdict, dataclass
import re


_WS = re.compile(r"\s+")


def _norm(value: str | None) -> str:
    return _WS.sub(" ", (value or "").strip())


@dataclass(frozen=True, slots=True)
class Showtime:
    movie: str
    show_date: str          # YYYY-MM-DD
    start_time: str         # HH:MM
    hall: str
    version: str = ""
    language: str = ""
    source_id: str = ""
    source: str = "maoyan"

    @property
    def key(self) -> str:
        # Keep the identity tied to what a user would regard as one concrete screening.
        return "|".join([
            _norm(self.show_date),
            _norm(self.start_time),
            _norm(self.hall).lower(),
            _norm(self.version).lower(),
        ])

    def to_dict(self) -> dict:
        return asdict(self)
