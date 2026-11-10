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
        "team_ids": [42637],
        "name": "Team C",
        "file": "team-C.ics",
    },
    {
        "team_ids": [6344],
        "name": "Team N",
        "file": "team-N.ics",
    },
    {
        "team_ids": [46147, 47821],
        "name": "Team F",
        "file": "team-F.ics",
    },
    {
        "team_ids": [39358],
        "name": "Team L",
        "file": "team-L.ics",
    },
    {
        "team_ids": [39358],
        "name": "Team G",
        "file": "team-G.ics",
    },
]


def parse_match_date(match):
    """Convert the Hockey.nl date to Europe/Amsterdam, preserving its clock time."""
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

    return datetime(
        year=original.year,
        month=original.month,
        day=original.day,
        hour=original.hour,
        minute=original.minute,
        second=original.second,
        microsecond=original.microsecond,
        tzinfo=AMSTERDAM_TIMEZONE,
    )


def match_team_id(match, team_ids):
    """Return the configured team ID participating in the match, if any."""
    home = match.get("home") or {}
    away = match.get("away") or {}

    for team_id in team_ids:
        if str(home.get("id")) == str(team_id):
            return team_id
        if str(away.get("id")) == str(team_id):
            return team_id

    return None


def get_opponent(match, team_ids):
    """Return the opponent of the selected team."""
    home = match.get("home") or {}
    away = match.get("away") or {}

    home_id = home.get("id")
    away_id = away.get("id")
    home_name = home.get("name", "Onbekend team")
    away_name = away.get("name", "Onbekend team")

    if any(str(home_id) == str(team_id) for team_id in team_ids):
        return away_name
    if any(str(away_id) == str(team_id) for team_id in team_ids):
        return home_name

    return f"{home_name} - {away_name}"


def get_location(match):
    """Return short location, full location, and city."""
    location = match.get("location") or {}
    facility = location.get("facility") or {}
    field = location.get("field") or {}

    facility_name = str(facility.get("name", "")).strip()
    field_name = str(field.get("name", "")).strip()
    address = str(facility.get("address", "")).strip()

    city = ""
    if address:
        address_lines = address.splitlines()
        if address_lines:
            parts = address_lines[-1].strip().split(maxsplit=1)
            if len(parts) == 2:
                city = parts[1]

    short_parts = [part for part in (facility_name, field_name) if part]
    short_location = " - ".join(short_parts)
    full_parts = [short_location] if short_location else []
    if address:
        full_parts.append(address.replace("\n", ", "))

    return short_location, ", ".join(full_parts), city


def create_event_uid(match, team_id, start):
    """Create a stable identifier for a calendar event."""
    match_id = match.get("id")
    if match_id is not None:
        return f"hockey-{match_id}-{team_id}@hockey-calendar"
    return f"hockey-{team_id}-{int(start.timestamp())}@hockey-calendar"


def create_calendar(team, matches):
    """Create one ICS calendar for one configured team."""
    calendar = Calendar()
    calendar.add("prodid", "-//Hockey Calendar Generator//NL")
    calendar.add("version", "2.0")
    calendar.add("calscale", "GREGORIAN")
    calendar.add("method", "PUBLISH")
    calendar.add("x-wr-calname", team["name"])
    calendar.add("x-wr-caldesc", "Automatisch bijgewerkt wedstrijdschema")
    calendar.add("x-wr-timezone", "Europe/Amsterdam")

    team_matches = []
    for match in matches:
        if not isinstance(match, dict):
            continue
        participating_team_id = match_team_id(match, team["team_ids"])
        if participating_team_id is None:
            continue
        start = parse_match_date(match)
        if start is not None:
            team_matches.append((start, match, participating_team_id))

    team_matches.sort(key=lambda item: item[0])
    events_added = 0
    seen_match_ids = set()

    for start, match, participating_team_id in team_matches:
        match_id = match.get("id")
        if match_id is not None and match_id in seen_match_ids:
            continue
        if match_id is not None:
            seen_match_ids.add(match_id)

        end = start + timedelta(hours=2)
        opponent = get_opponent(match, team["team_ids"])
        short_location, full_location, _city = get_location(match)
        summary = f"{opponent} | {short_location}" if short_location else opponent

        event = Event()
        event.add(
            "uid",
            create_event_uid(match, participating_team_id, start),
        )
        event.add("summary", summary)
        event.add("dtstart", start)
        event.add("dtend", end)
        event.add("dtstamp", datetime.now(timezone.utc))
        event.add("last-modified", datetime.now(timezone.utc))

        if full_location:
            event.add("location", full_location)

        status = str(match.get("status", "")).lower()
        event.add(
            "status",
            "CANCELLED"
            if status in {"cancelled", "canceled", "afgelast"}
            else "CONFIRMED",
        )
        calendar.add_component(event)
        events_added += 1

    return calendar, events_added


def create_index_page(results):
    """Create a GitHub Pages index with calendar links."""
    links = []
    for result in results:
        filename = html.escape(result["file"])
        name = html.escape(result["name"])
        events = result["events"]
        links.append(
            "<li>"
            f'<a href="{filename}">{name}</a> '
            f"({events} wedstrijden)"
            "</li>"
        )

    updated_at = datetime.now(AMSTERDAM_TIMEZONE).strftime("%d-%m-%Y %H:%M")
    page = f"""<!doctype html>
<html lang="nl">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Hockeyagenda's</title>
    <style>
        body {{ max-width: 800px; margin: 40px auto; padding: 0 20px;
            font-family: Arial, sans-serif; line-height: 1.6; color: #222; }}
        h1 {{ color: #163d68; }}
        li {{ margin: 12px 0; }}
        a {{ color: #0067b8; font-weight: bold; }}
        .updated {{ margin-top: 30px; color: #666; font-size: 14px; }}
    </style>
</head>
<body>
    <h1>Hockeyagenda's</h1>
    <p>Klik op een team om het ICS-bestand te openen.</p>
    <ul>
        {''.join(links)}
    </ul>
    <p class="updated">Laatst bijgewerkt: {updated_at}</p>
</body>
</html>
"""

    index_file = OUTPUT_DIR / "index.html"
    index_file.write_text(page, encoding="utf-8")


def verify_calendar_timezone(output_file):
    """Verify that the output does not contain fixed-offset TZIDs."""
    content = output_file.read_text(encoding="utf-8")
    invalid_values = [
        'TZID="UTC+01:00"',
        'TZID="UTC+02:00"',
        "TZID=UTC+01:00",
        "TZID=UTC+02:00",
    ]
    for invalid_value in invalid_values:
        if invalid_value in content:
            raise RuntimeError(
                f"Verkeerde tijdzone gevonden in {output_file}: {invalid_value}"
            )

    event_lines = [
        line
        for line in content.splitlines()
        if line.startswith("DTSTART") or line.startswith("DTEND")
    ]
    if event_lines:
        print(f"Tijdzonecontrole voor {output_file}:")
        for line in event_lines[:4]:
            print(f"  {line}")


async def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    matches_cache = {}

    print("HockeyWeerelt API initialiseren")
    async with await Api.create() as api:
        print("API succesvol geïnitialiseerd")

        for team in TEAMS:
            team_ids = team["team_ids"]
            print("")
            print("=" * 60)
            print(f"Team verwerken: {team['name']}")
            print(f"Team-ID's: {', '.join(map(str, team_ids))}")

            matches_by_id = {}
            for team_id in team_ids:
                if team_id not in matches_cache:
                    print(f"Wedstrijden ophalen voor team-ID {team_id}...")
                    matches_cache[team_id] = await api.get_matches_for_teams(
                        [team_id]
                    )
                    print(
                        f"{len(matches_cache[team_id])} wedstrijden ontvangen"
                    )
                    await asyncio.sleep(15)

                for match in matches_cache[team_id]:
                    match_id = match.get("id") if isinstance(match, dict) else None
                    # Preserve matches without an ID while de-duplicating known IDs.
                    key = ("id", match_id) if match_id is not None else (
                        "object", id(match)
                    )
                    matches_by_id[key] = match

            calendar, events_added = create_calendar(
                team,
                list(matches_by_id.values()),
            )
            output_file = OUTPUT_DIR / team["file"]
            output_file.write_bytes(calendar.to_ical())
            verify_calendar_timezone(output_file)

            results.append(
                {
                    "name": team["name"],
                    "file": team["file"],
                    "events": events_added,
                }
            )
            print(
                f"{output_file} aangemaakt met {events_added} wedstrijden"
            )

    create_index_page(results)
    print("")
    print("Alle kalenderbestanden zijn aangemaakt:")
    for result in results:
        print(f"- {result['file']}: {result['events']} wedstrijden")


if __name__ == "__main__":
    asyncio.run(main())
