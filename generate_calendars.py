import asyncio
import hashlib
import html
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from dateutil import parser
from icalendar import Calendar, Event

from hockeyweerelt import Api


TEAMS = [
    {
        "team_id": 42637,
        "poule_id": 183108,
        "calendar_name": "Hockey team 42637",
        "filename": "team-42637.ics",
    },
    {
        "team_id": 6344,
        "poule_id": 182127,
        "calendar_name": "Hockey team 6344",
        "filename": "team-6344.ics",
    },
    {
        "team_id": 46147,
        "poule_id": 182243,
        "calendar_name": "Hockey team 46147",
        "filename": "team-46147.ics",
    },
    {
        "team_id": 39358,
        "poule_id": 182090,
        "calendar_name": "Hockey team 39358",
        "filename": "team-39358.ics",
    },
]


OUTPUT_DIRECTORY = Path("public")
AMSTERDAM_TIMEZONE = ZoneInfo("Europe/Amsterdam")


def first_value(data, keys, default=None):
    """Return the first existing non-empty value."""
    if not isinstance(data, dict):
        return default

    for key in keys:
        value = data.get(key)

        if value not in (None, ""):
            return value

    return default


def object_name(value, default="Onbekend"):
    """Extract a readable name from a string or dictionary."""
    if isinstance(value, str):
        return value.strip() or default

    if isinstance(value, dict):
        name = first_value(
            value,
            [
                "name",
                "display_name",
                "displayName",
                "short_name",
                "shortName",
                "club_name",
                "clubName",
                "title",
                "description",
            ],
        )

        if name:
            return str(name).strip()

    if value not in (None, ""):
        return str(value)

    return default


def get_team_name(match, side):
    """Return the home or away team name."""
    if side == "home":
        keys = [
            "home",
            "home_team",
            "homeTeam",
            "home_team_name",
            "homeTeamName",
        ]
    else:
        keys = [
            "away",
            "away_team",
            "awayTeam",
            "away_team_name",
            "awayTeamName",
        ]

    value = first_value(match, keys)

    return object_name(
        value,
        default="Onbekend team",
    )


def get_location(match):
    """Create a readable location string."""
    location = first_value(
        match,
        [
            "location",
            "venue",
            "accommodation",
            "complex",
        ],
    )

    parts = []

    if isinstance(location, str):
        parts.append(location)

    elif isinstance(location, dict):
        location_key_groups = [
            ["name", "description", "title"],
            ["address", "street"],
            ["postal_code", "postalCode", "zipcode"],
            ["city", "place"],
        ]

        for keys in location_key_groups:
            value = first_value(location, keys)

            if value:
                parts.append(str(value))

    field = first_value(
        match,
        [
            "field",
            "field_number",
            "fieldNumber",
            "pitch",
        ],
    )

    if isinstance(field, dict):
        field = object_name(field, default="")

    if field:
        field_text = str(field).strip()

        if not field_text.lower().startswith("veld"):
            field_text = f"Veld {field_text}"

        parts.append(field_text)

    unique_parts = []

    for part in parts:
        cleaned = str(part).strip()

        if cleaned and cleaned not in unique_parts:
            unique_parts.append(cleaned)

    return ", ".join(unique_parts)
