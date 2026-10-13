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
        "name": "Team G",
        "file": "team-G.ics",
    },
]


def parse_match_date(match):
    """
    Convert the Hockey.nl date to Europe/Amsterdam.

    The clock time supplied by Hockey.nl is preserved.

    Example:
    2026-10-23T20:30:00+02:00

    becomes:
    2026-10-23 20:30:00 Europe/Amsterdam
    """
    match_date = match.get("date")

    if not match_date:
        return None

    try:
        original = datetime.fromisoformat(
            str(match_date).replace("Z", "+00:00")
        )
    except (ValueError, TypeError):
        print(
            "Wedstrijd overgeslagen vanwege "
            f"ongeldige datum: {match_date}"
        )
        return None

    # Maak bewust een nieuwe datetime aan met de IANA-tijdzone
    # Europe/Amsterdam. Hiermee voorkomen we TZID="UTC+02:00".
    start = datetime(
        year=original.year,
        month=original.month,
        day=original.day,
        hour=original.hour,
        minute=original.minute,
        second=original.second,
        microsecond=original.microsecond,
        tzinfo=AMSTERDAM_TIMEZONE,
    )

    return start


def match_involves_team(match, team_id):
    """Check whether the selected team plays in the match."""
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
    Return a short and full location.

    Short location is used in the subject.
    Full location is used in the ICS LOCATION field.
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
    """Create a stable identifier for a calendar event."""
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

        # Standaard wedstrijdduur: twee uur.
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

        # Beide waarden hebben expliciet ZoneInfo
        # met de naam Europe/Amsterdam.
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
            f'{filename}{name}</a> '
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


def verify_calendar_timezone(output_file):
    """
    Verify that the output does not contain fixed-offset TZIDs.

    The workflow stops if UTC+01:00 or UTC+02:00 is found.
    """
    content = output_file.read_text(
        encoding="utf-8",
    )

    invalid_values = [
        'TZID="UTC+01:00"',
        'TZID="UTC+02:00"',
        "TZID=UTC+01:00",
        "TZID=UTC+02:00",
    ]

    for invalid_value in invalid_values:
        if invalid_value in content:
            raise RuntimeError(
                f"Verkeerde tijdzone gevonden in "
                f"{output_file}: {invalid_value}"
            )

    event_lines = [
        line
        for line in content.splitlines()
        if (
            line.startswith("DTSTART")
            or line.startswith("DTEND")
        )
    ]

    if event_lines:
        print(
            f"Tijdzonecontrole voor {output_file}:"
        )

        for line in event_lines[:4]:
            print(f"  {line}")

async def main():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    results = []

    # Cache voorkomt dubbele API-calls.
    # Team L en Team GL gebruiken hetzelfde team-ID.
    matches_cache = {}

    print("HockeyWeerelt API initialiseren")

    async with await Api.create() as api:
        print("API succesvol geïnitialiseerd")

        for team in TEAMS:
            team_id = team["team_id"]

            print("")
            print("=" * 60)
            print(f"Team verwerken: {team['name']}")
            print(f"Team-ID: {team_id}")

            if team_id in matches_cache:
                print(
                    "Wedstrijden uit cache gebruiken."
                )

                matches = matches_cache[team_id]

            else:
                print(
                    "Wedstrijden ophalen bij HockeyWeerelt..."
                )

                matches = (
                    await api.get_matches_for_teams(
                        [team_id]
                    )
                )

                matches_cache[team_id] = matches

                print(
                    f"{len(matches)} wedstrijden ontvangen"
                )

                # Voorkom te veel API-requests vlak achter elkaar.
                await asyncio.sleep(3)

            calendar, events_added = create_calendar(
                team,
                matches,
            )

            output_file = (
                OUTPUT_DIR / team["file"]
            )

            output_file.write_bytes(
                calendar.to_ical()
            )

            verify_calendar_timezone(
                output_file
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
