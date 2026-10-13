import asyncio
import html
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from hockeyweerelt import Api
from icalendar import Calendar, Event


OUTPUT_DIR = Path("public")
AMSTERDAM_TIMEZONE = ZoneInfo("Europe/Amsterdam")


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
        "name": "Team L",
        "file": "team-L.ics",
    },
    {
        "team_id": 39358,
        "name": "Team GL",
        "file": "team-GL.ics",
    },
]


def parse_match_date(match):
    """
    Convert the Hockey.nl date to Dutch local time.

    Example input:
    2026-09-04T20:30:00+02:00
    """
    match_date = match.get("date")

    if not match_date:
        return None

    try:
        start = datetime.fromisoformat(
            str(match_date).replace("Z", "+00:00")
        )
    except ValueError:
        print(
            f"Wedstrijd overgeslagen vanwege "
            f"ongeldige datum: {match_date}"
        )
        return None

    if start.tzinfo is None:
        start = start.replace(
            tzinfo=AMSTERDAM_TIMEZONE
        )
    else:
        start = start.astimezone(
            AMSTERDAM_TIMEZONE
        )

    return start


def match_involves_team(match, team_id):
    """Check whether the selected team plays in this match."""
    home = match.get("home") or {}
    away = match.get("away") or {}

    home_id = home.get("id")
    away_id = away.get("id")

    return (
        str(home_id) == str(team_id)
        or str(away_id) == str(team_id)
    )


def get_opponent(match, team_id):
    """Return the opponent of the selected team."""
    home = match.get("home") or {}
    away = match.get("away") or {}

    home_id = home.get("id")
    away_id = away.get("id")

    home_name = home.get(
        "name",
        "Onbekend team",
    )
    away_name = away.get(
        "name",
        "Onbekend team",
    )

    if str(home_id) == str(team_id):
        return away_name

    if str(away_id) == str(team_id):
        return home_name

    return f"{home_name} - {away_name}"


def get_location(match):
    """
    Return two location strings:

    1. Short location for the calendar subject.
    2. Full location for the ICS location field.
    """
    location = match.get("location") or {}
    facility = location.get("facility") or {}
    field = location.get("field") or {}

    facility_name = str(
        facility.get("name", "")
    ).strip()

    field_name = str(
        field.get("name", "")
    ).strip()

    address = str(
        facility.get("address", "")
    ).strip()

    short_parts = []

    if facility_name:
        short_parts.append(facility_name)

    if field_name:
        short_parts.append(field_name)

    short_location = " - ".join(short_parts)

    full_parts = []

    if short_location:
        full_parts.append(short_location)

    if address:
        full_parts.append(
            address.replace("\n", ", ")
        )

    full_location = ", ".join(full_parts)

    return short_location, full_location


def create_event_uid(match, team_id, start):
    """Create a stable unique identifier for the event."""
    match_id = match.get("id")

    if match_id is not None:
        return (
            f"hockey-{match_id}-"
            f"{team_id}@hockey-calendar"
        )

    return (
        f"hockey-{team_id}-"
        f"{int(start.timestamp())}@hockey-calendar"
    )


def create_calendar(team, matches):
    """Create one ICS calendar for one configured team."""
    calendar = Calendar()

    calendar.add(
        "prodid",
        "-//Hockey Calendar Generator//NL",
    )
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("method", "PUBLISH")

    calendar.add(
        "x-wr-calname",
        team["name"],
    )
    calendar.add(
        "x-wr-caldesc",
        "Automatisch bijgewerkt wedstrijdschema",
    )
    calendar.add(
        "x-wr-timezone",
        "Europe/Amsterdam",
    )

    team_matches = []

    for match in matches:
        if not isinstance(match, dict):
            continue

        if not match_involves_team(
            match,
            team["team_id"],
        ):
            continue

        start = parse_match_date(match)

        if start is None:
            continue

        team_matches.append(
            (start, match)
        )

    team_matches.sort(
        key=lambda item: item[0]
    )

    events_added = 0
    seen_match_ids = set()

    for start, match in team_matches:
        match_id = match.get("id")

        if (
            match_id is not None
            and match_id in seen_match_ids
        ):
            continue

        if match_id is not None:
            seen_match_ids.add(match_id)

        # Standaard wedstrijdduur van twee uur.
        end = start + timedelta(hours=2)

        opponent = get_opponent(
            match,
            team["team_id"],
        )

        short_location, full_location = (
            get_location(match)
        )

        if short_location:
            summary = (
                f"{opponent} | {short_location}"
            )
        else:
            summary = opponent

        event = Event()

        event.add(
            "uid",
            create_event_uid(
                match,
                team["team_id"],
                start,
            ),
        )

        event.add("summary", summary)

        # De datums hebben expliciet de tijdzone
        # Europe/Amsterdam.
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
            event.add(
                "location",
                full_location,
            )

        status = str(
            match.get("status", "")
        ).lower()

        if status in {
            "cancelled",
            "canceled",
            "afgelast",
        }:
            event.add(
                "status",
                "CANCELLED",
            )
        else:
            event.add(
                "status",
                "CONFIRMED",
            )

        calendar.add_component(event)
        events_added += 1

    return calendar, events_added


def create_index_page(results):
    """Create a GitHub Pages index with calendar links."""
    links = []

    for result in results:
        filename = html.escape(
            result["file"]
        )
        name = html.escape(
            result["name"]
        )
        events = result["events"]

        link = (
            "<li>"
            f'{name}</a> '
            f"({events} wedstrijden)"
            "</li>"
        )

        links.append(link)

    updated_at = datetime.now(
        AMSTERDAM_TIMEZONE
    ).strftime("%d-%m-%Y %H:%M")

    page = f"""<!doctype html>
<html lang="nl">
<head>
    <meta charset="utf-8">
    <meta
        name="viewport"
        content="width=device-width, initial-scale=1"
    >
    <title>Hockeyagenda's</title>

    <style>
        body {{
            max-width: 800px;
            margin: 40px auto;
            padding: 0 20px;
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #222;
        }}

        h1 {{
            color: #163d68;
        }}

        li {{
            margin: 12px 0;
        }}

        a {{
            color: #0067b8;
            font-weight: bold;
        }}

        .updated {{
            margin-top: 30px;
            color: #666;
            font-size: 14px;
        }}
    </style>
</head>

<body>
    <h1>Hockeyagenda's</h1>

    <p>
        Klik op een team om het ICS-bestand te openen.
    </p>

    <ul>
        {''.join(links)}
    </ul>

    <p class="updated">
        Laatst bijgewerkt: {updated_at}
    </p>
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

    # Unieke team-ID's verzamelen.
    # Team L en Team GL hebben hetzelfde team-ID,
    # dus dit team wordt maar één keer opgehaald.
    unique_team_ids = list(
        dict.fromkeys(
            team["team_id"]
            for team in TEAMS
        )
    )

    print("HockeyWeerelt API initialiseren")
    print(
        f"Unieke team-ID's: {unique_team_ids}"
    )

    async with await Api.create() as api:
        print("API succesvol geïnitialiseerd")

        # Eén gecombineerde API-aanvraag voor alle
        # unieke teams. Dit beperkt de kans op een
        # 429 Too Many Requests-fout.
        print("Wedstrijden ophalen")

        all_matches = (
            await api.get_matches_for_teams(
                unique_team_ids
            )
        )

        print(
            f"{len(all_matches)} wedstrijden "
            f"ontvangen"
        )

        for team in TEAMS:
            print("")
            print("=" * 60)
            print(
                f"Team verwerken: {team['name']}"
            )
            print(
                f"Team-ID: {team['team_id']}"
            )

            calendar, events_added = (
                create_calendar(
                    team,
                    all_matches,
                )
            )

            output_file = (
                OUTPUT_DIR / team["file"]
            )

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
    print(
        "Alle kalenderbestanden zijn aangemaakt:"
    )

    for result in results:
        print(
            f"- {result['file']}: "
            f"{result['events']} wedstrijden"
        )


if __name__ == "__main__":
    asyncio.run(main())
