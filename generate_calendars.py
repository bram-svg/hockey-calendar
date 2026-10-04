import asyncio
from pathlib import Path

from icalendar import Calendar, Event
from dateutil import parser

from hockeyweerelt import Api


async def main():

    async with await Api.create() as api:

        matches = await api.get_team_matches(
            42637,
            183108,
        )

        cal = Calendar()
        cal.add("prodid", "-//Hockey Calendar//NL")
        cal.add("version", "2.0")

        for match in matches:

            event = Event()

            start = parser.isoparse(match["date"])
            end = start.replace(hour=start.hour + 2)

            summary = (
                f'{match["home"]["name"]} - '
                f'{match["away"]["name"]}'
            )

            location = (
                match["location"]["facility"]["name"]
            )

            event.add("summary", summary)
            event.add("dtstart", start)
            event.add("dtend", end)
            event.add("location", location)

            cal.add_component(event)

        Path("public").mkdir(exist_ok=True)

        with open(
            "public/team-42637.ics",
            "wb",
        ) as f:
            f.write(cal.to_ical())

        print("ICS bestand gemaakt")


asyncio.run(main())
