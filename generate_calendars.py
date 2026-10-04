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
    "mc/teams/{team_id}/matches/upcoming?show_all=0"
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
    """Create one iCalendar file for one hockey team."""
    calendar = Calendar()

    calendar.add(
        "prodid",
        "-//Hockey.nl Calendar Generator//NL",
    )
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("method", "PUBLISH")
    calendar.add(
        "x-wr-calname",
        team["calendar_name"],
    )
    calendar.add(
        "x-wr-caldesc",
        "Automatisch bijgewerkt via het Hockey.nl Match Center",
    )
    calendar.add(
        "x-wr-timezone",
        "Europe/Amsterdam",
    )

    events_added = 0

    for match in matches:
        datetime_value = match.get("datetime")

        if not datetime_value:
            print(
                "Wedstrijd overgeslagen omdat de datum ontbreekt"
            )
            continue

        try:
            start = parser.isoparse(str(datetime_value))
        except ValueError:
            print(
                f"Ongeldige wedstrijddatum: {datetime_value}"
            )
            continue

        # De API-datum behoort een tijdzone te bevatten.
        # Wanneer die ontbreekt, behandelen we de waarde als UTC.
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)

        end = start + timedelta(hours=2)

        home_team = get_team_name(
            match.get("home_team")
        )
        away_team = get_team_name(
            match.get("away_team")
        )

        location = get_location(match)

        uid = get_match_uid(
            match=match,
            team_id=team["team_id"],
            start=start,
            home_team=home_team,
            away_team=away_team,
        )

        event = Event()

        event.add("uid", uid)
        event.add("summary", f"{home_team} - {away_team}")
        event.add("dtstart", start)
        event.add("dtend", end)
        event.add("dtstamp", datetime.now(timezone.utc))
        event.add("last-modified", datetime.now(timezone.utc))
        event.add("status", "CONFIRMED")

        if location:
            event.add("location", location)

        description = [
            "Automatisch overgenomen uit Hockey.nl.",
        ]

        competition = match.get("competition")
        poule = match.get("poule")
        field = match.get("field")

        if competition:
            description.append(
                f"Competitie: {competition}"
            )

        if poule:
            description.append(
                f"Poule: {poule}"
            )

        if field:
            description.append(
                f"Veld: {field}"
            )

        description.append(
            f"Team-ID: {team['team_id']}"
        )

        event.add(
            "description",
            "\n".join(description),
        )

        calendar.add_component(event)
        events_added += 1

    return calendar, events_added


def create_index_page(results):
    """Create a simple page containing the four calendar links."""
    links = []

    for result in results:
        links.append(
            f"""
            <li>
                {result['filename']}
                    {result['calendar_name']}
                </a>
                ({result['events']} wedstrijden)
            </li>
            """
        )

    html = f"""<!doctype html>
<html lang="nl">
<head>
    <meta charset="utf-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >
    <title>Hockeykalenders</title>
</head>
<body>
    <h1>Hockeykalenders</h1>
    <p>
        Selecteer een kalender om het ICS-bestand te openen.
    </p>
    <ul>
        {''.join(links)}
    </ul>
</body>
</html>
"""

    index_file = OUTPUT_DIRECTORY / "index.html"
    index_file.write_text(html, encoding="utf-8")


def main():
    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    results = []

    for team in TEAMS:
        matches = fetch_matches(team["team_id"])

        calendar, events_added = create_calendar(
            team,
            matches,
        )

        output_file = (
            OUTPUT_DIRECTORY / team["filename"]
        )

        output_file.write_bytes(
            calendar.to_ical()
        )

        results.append(
            {
                "calendar_name": team["calendar_name"],
                "filename": team["filename"],
                "events": events_added,
            }
        )

        print(
            f"{output_file} aangemaakt met "
            f"{events_added} wedstrijden"
        )

    create_index_page(results)

    print("Alle vier kalenders zijn aangemaakt.")


if __name__ == "__main__":
    main()
