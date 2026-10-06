"""
Works out when each video should go public: the next 10 pm (by default US Eastern).

The pipeline uploads a video privately a few hours early and asks YouTube to make it public at
that exact moment (`publishAt`), so GitHub's late starts and YouTube's processing time do not
matter. The clock is handled in the chosen time zone, so summer/winter time changes are automatic.
"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def _parse_clock(text: str):
    hour, minute = text.strip().split(":")
    return int(hour), int(minute)


def _clock_for(day, clock):
    """`clock` is either one time for every day ("22:00") or a {weekday: "HH:MM"} map
    where Monday = 0 ... Sunday = 6."""
    if isinstance(clock, dict):
        return _parse_clock(clock[day.weekday()])
    return _parse_clock(clock)


def next_publish_slot(now_utc: datetime, used, clock="22:00",
                      tz_name: str = "America/New_York", min_lead_minutes: int = 90) -> datetime:
    """The next publish time in `tz_name` that is at least `min_lead_minutes` away and later
    than any slot already handed out (so two videos never go public together). UTC result."""
    tz = ZoneInfo(tz_name)
    earliest = now_utc + timedelta(minutes=min_lead_minutes)

    taken = []
    for entry in used or []:
        stamp = entry.get("publish_at") if isinstance(entry, dict) else None
        if stamp:
            taken.append(datetime.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc))
    if taken:
        earliest = max(earliest, max(taken) + timedelta(minutes=1))

    day = earliest.astimezone(tz).date()
    while True:
        hour, minute = _clock_for(day, clock)
        # Build the wall-clock time in the zone itself, so daylight saving is handled correctly.
        candidate = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
        if candidate.astimezone(timezone.utc) >= earliest:
            return candidate.astimezone(timezone.utc)
        day += timedelta(days=1)


def to_youtube_time(moment_utc: datetime) -> str:
    """The format YouTube's `publishAt` wants, e.g. 2026-10-07T02:00:00Z."""
    return moment_utc.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def describe_slot(moment_utc: datetime, tz_name: str = "America/New_York") -> str:
    local = moment_utc.astimezone(ZoneInfo(tz_name))
    return f"{local.strftime('%I:%M %p').lstrip('0')} {local.tzname()} on {local.date()} ({to_youtube_time(moment_utc)})"
