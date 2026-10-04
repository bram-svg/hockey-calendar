import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from icalendar import Calendar, Event

from hockeyweerelt import Api

OUTPUT_DIR = Path("public")

TEAMS = [
    {
        "team_id": 42637,
        "poule_id": 183108,
        "name": "Team C",
        "file": "team-C.ics",
    },
    {
        "team_id": 6344,
        "poule_id": 182127,
        "name": "Team N",
        "file": "team-N.ics",
    },
    {
        "team_id": 46147,
        "poule_id": 182243,
        "name": "Team F",
        "file": "team-F.ics",
    },
    {
        "team_id": 39358,
        "poule_id": 182090,
        "name": "Team GL",
        "file": "team-GL.ics",
    },
]


def create_calendar(team_name, matches):
    cal = Calendar()
    cal.add("prodid", "-//Hockey Calendar//NL")
    cal.add("version", "2.0")
    cal.add("x-wr-calname", team_name)

    for match in matches:

        match_date = match.get("date")
        if not match_date:
            continue

        start = datetime.fromisoformat(
            match_date.replace("Z", "+00:00")
        )

        end = start + timedelta(hours=2)

        home = match.get("home", {})
        away = match.get("away", {})

        home_name = home.get("name", "Unknown")
        away_name = away.get("name", "Unknown")

        ev = Event()

        ev.add(
            "uid",
            f"{match.get('id', start.timestamp())}@hockey"
        )

        location = match.get("accommodation", {})
        location_name = ""

        if isinstance(location, dict):
            location_name = (
              location.get("name")
              or location.get("description")
              or ""
           )

ev.add(
    "summary",
    f"{away_name} @ {location_name}"
)
        ev.add("dtstart", start)
        ev.add("dtend", end)

        ev.add(
            "dtstamp",
            datetime.utcnow()
        )

        if match.get("status") == "cancelled":
            ev.add("status", "CANCELLED")
        else:
            ev.add("status", "CONFIRMED")

        cal.add_component(ev)

    return cal


async def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    async with await Api.create() as api:

        for team in TEAMS:

            print(
                f"Processing {team['name']}"
            )

            matches = await api.get_team_matches(
                team["team_id"],
                team["poule_id"],
            )

            print(
                f"Matches found: {len(matches)}"
            )

            cal = create_calendar(
                team["name"],
                matches,
            )

            output_file = (
                OUTPUT_DIR / team["file"]
            )

            output_file.write_bytes(
                cal.to_ical()
            )

            print(
                f"Written: {output_file}"
            )

    print("Finished")


if __name__ == "__main__":
    asyncio.run(main())
