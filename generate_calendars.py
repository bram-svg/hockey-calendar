import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path

from icalendar import Calendar, Event
from hockeyweerelt import Api


OUTPUT_DIR = Path("public")

TEAMS = [
    {
        "team_id": 42637,
        "name": "Team C",
        "file": "team-C.ics",
    },
    {
        "team_id": 6344,
        "name": "Team N",
        "file": "team-N.ics",
    },
    {
        "team_id": 46147,
        "name": "Team F",
        "file": "team-F.ics",
    },
    {
        "team_id": 39358,
        "name": "Team GL",
        "file": "team-GL.ics",
    },
]


def parse_match_date(match):
    """Convert the Hockey.nl date to a Python datetime."""
    match_date = match.get("date")

    if not match_date:
        return None

    try:
        return datetime.fromisoformat(
            str(match_date).replace("Z", "+00:00")
        )
    except ValueError:
        print(f"Ongeldige datum overgeslagen: {match_date}")
        return None


def get_opponent(match, team_id):
    """Determine the opponent based on the current team ID."""
    home = match.get("home") or {}
    away = match.get("away") or {}

    home_id = home.get("id")
    away_id = away.get("id")

    home_name = home.get("name", "Onbekend team")
    away_name = away.get("name", "Onbekend team")

    if str(home_id) == str(team_id):
        return away_name

    if str(away_id) == str(team_id):
        return home_name

    return f"{home_name} - {away_name}"


def get_location(match):
    """Return location and field as one readable string."""
    location = match.get("location") or {}
    facility = location.get("facility") or {}
    field = location.get("field") or {}

    facility_name = facility.get("name", "")
    field_name = field.get("name", "")
    address = facility.get("address", "")

    subject_parts = []

    if facility_name:
        subject_parts.append(str(facility_name))

    if field_name:
        subject_parts.append(str(field_name))

    subject_location = " - ".join(subject_parts)

    calendar_parts = []

    if subject_location:
        calendar_parts.append(subject_location)

    if address:
        calendar_parts.append(
            str(address).replace("\n", ", ")
        )

    full_location = ", ".join(calendar_parts)

    return subject_location, full_location


def create_calendar(team, matches):
    """Create one ICS calendar for one team."""
    calendar = Calendar()

    calendar.add(
        "prodid",
        "-//Hockey Calendar Generator//NL",
    )
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("method", "PUBLISH")
    calendar.add("x-wr-calname", team["name"])
    calendar.add(
        "x-wr-caldesc",
        "Automatisch bijgewerkt wedstrijdschema",
    )
    calendar.add(
        "x-wr-timezone",
        "Europe/Amsterdam",
    )

    events_added = 0
    seen_match_ids = set()

    matches_with_dates = []

    for match in matches:
        if not isinstance(match, dict):
            continue

        start = parse_match_date(match)

        if start is not None:
            matches_with_dates.append((start, match))

    matches_with_dates.sort(
        key=lambda item: item[0]
    )

    for start, match in matches_with_dates:
        match_id = match.get("id")

        if match_id in seen_match_ids:
            continue

        if match_id is not None:
            seen_match_ids.add(match_id)

        end = start + timedelta(hours=2)

        opponent = get_opponent(
            match,
            team["team_id"],
        )

        subject_location, full_location = get_location(
            match
        )

        if subject_location:
            summary = (
                f"{opponent} | {subject_location}"
            )
        else:
            summary = opponent

        event = Event()

        if match_id is not None:
            uid = (
                f"hockey-{match_id}-"
                f"{team['team_id']}@hockey-calendar"
            )
        else:
            uid = (
                f"hockey-{team['team_id']}-"
                f"{int(start.timestamp())}@hockey-calendar"
            )

        event.add("uid", uid)
        event.add("summary", summary)
        event.add("dtstart", start)
        event.add("dtend", end)
        event.add(
            "dtstamp",
            datetime.now(timezone.utc),
        )
        event.add(
            "last-modified",
            datetime.now(timezone.utc),
        )

        if full_location:
            event.add("location", full_location)

        status = str(
            match.get("status", "")
        ).lower()

        if status in {
            "cancelled",
            "canceled",
            "afgelast",
        }:
            event.add("status", "CANCELLED")
        else:
            event.add("status", "CONFIRMED")

        calendar.add_component(event)
        events_added += 1

    return calendar, events_added

def create_index_page(results):
    """Create a simple page with links to the calendars."""

    links = []

    for result in results:
        filename = result["file"]
        name = result["name"]
        events = result["events"]

        link = (
            '<li>'
            + filename
            + ''
            + name
            + "</a> ("
            + str(events)
            + " wedstrijden)</li>"
        )

        links.append(link)

    page = """<!doctype html>
<html lang="nl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Hockeyagenda's</title>
</head>
<body>
    <h1>Hockeyagenda's</h1>
    <p>Kies een team:</p>
    <ul>
"""

    page += "\n".join(links)

    page += """
    </ul>
</body>
</html>
"""

    index_file = OUTPUT_DIR / "index.html"

    index_file.write_text(
        page,
        encoding="utf-8",
    )

async def main():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results = []

    print("HockeyWeerelt API initialiseren")

    async with await Api.create() as api:
        print("API succesvol geïnitialiseerd")

        for team in TEAMS:
            print("")
            print("=" * 60)
            print(f"Team verwerken: {team['name']}")
            print(f"Team-ID: {team['team_id']}")

            matches = await api.get_matches_for_teams(
                [team["team_id"]]
            )

            print(
                f"{len(matches)} wedstrijden ontvangen"
            )

            calendar, events_added = create_calendar(
                team,
                matches,
            )

            output_file = OUTPUT_DIR / team["file"]

            output_file.write_bytes(
                calendar.to_ical()
            )

            results.append(
                {
                    "name": team["name"],
                    "file": team["file"],
                    "events": events_added,
                }
            )

            print(
                f"{output_file} aangemaakt met "
                f"{events_added} wedstrijden"
            )

    create_index_page(results)

    print("")
    print("Alle kalenderbestanden zijn aangemaakt:")

    for result in results:
        print(
            f"- {result['file']}: "
            f"{result['events']} wedstrijden"
        )


if __name__ == "__main__":
    asyncio.run(main())
