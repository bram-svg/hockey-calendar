import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from dateutil import parser
from icalendar import Calendar, Event


# De vier team-ID's uit de Hockey.nl-links.
TEAMS = [
    {
        "team_id": 42637,
        "calendar_name": "Hockey team 42637",
        "filename": "team-42637.ics",
    },
    {
        "team_id": 6344,
        "calendar_name": "Hockey team 6344",
        "filename": "team-6344.ics",
    },
    {
        "team_id": 46147,
        "calendar_name": "Hockey team 46147",
        "filename": "team-46147.ics",
    },
    {
        "team_id": 39358,
        "calendar_name": "Hockey team 39358",
        "filename": "team-39358.ics",
    },
]

API_URL = (
    "https://publicaties.hockeyweerelt.nl/"
    "mc/teams/{team_id}/matches/upcoming"
)

OUTPUT_DIRECTORY = Path("public")

HEADERS = {
    "Accept": "application/json",
    "User-Agent": "personal-hockey-calendar/1.0",
}


def get_team_name(team_data):
    """Return the most useful team name from an API object."""
    if not isinstance(team_data, dict):
        return "Onbekend team"

    team_name = (
        team_data.get("name")
        or team_data.get("short_name")
        or team_data.get("club_name")
    )

    return str(team_name or "Onbekend team")


def get_location(match):
    """Create a readable location from the API response."""
    location = match.get("location")

    if isinstance(location, str):
        return location

    if not isinstance(location, dict):
        location = {}

    parts = []

    description = location.get("description")
    street = location.get("street")
    city = location.get("city")
    field = match.get("field")

    if description:
        parts.append(str(description))

    if street:
        parts.append(str(street))

    if city:
        parts.append(str(city))

    if field:
        parts.append(f"Veld {field}")

    return ", ".join(parts)


def get_match_uid(match, team_id, start, home_team, away_team):
    """
    Create a stable identifier.

    A stable UID prevents calendar applications from creating
    a duplicate appointment after every update.
    """
    match_id = (
        match.get("id")
        or match.get("match_id")
        or match.get("matchId")
    )

    if match_id:
        return f"hockey-{match_id}@hockey-calendars"

    value = (
        f"{team_id}|{start.isoformat()}|"
        f"{home_team}|{away_team}"
    )

    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()

    return f"hockey-{digest[:24]}@hockey-calendars"


def fetch_matches(team_id):
    """Retrieve upcoming matches for one team."""
    url = API_URL.format(team_id=team_id)

    print(f"Wedstrijden ophalen voor team {team_id}")

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    if isinstance(payload, dict):
        matches = payload.get("data", [])
    elif isinstance(payload, list):
        matches = payload
    else:
        matches = []

    if not isinstance(matches, list):
        raise RuntimeError(
            f"Onverwacht antwoord voor team {team_id}"
        )

    print(
        f"{len(matches)} aankomende wedstrijden gevonden "
        f"voor team {team_id}"
    )

    return matches


def create_calendar(team, matches):
