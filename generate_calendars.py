from pathlib import Path
import json
import requests

TEAMS = [
    {
        "team_id": 42637,
        "poule_id": 183108,
        "calendar_name": "Team 42637",
        "filename": "team-42637.ics",
    },
    {
        "team_id": 6344,
        "poule_id": 182127,
        "calendar_name": "Team 6344",
        "filename": "team-6344.ics",
    },
    {
        "team_id": 46147,
        "poule_id": 182243,
        "calendar_name": "Team 46147",
        "filename": "team-46147.ics",
    },
    {
        "team_id": 39358,
        "poule_id": 182090,
        "calendar_name": "Team 39358",
        "filename": "team-39358.ics",
    },
]


def fetch_team(team_id, poule_id):

    url = (
        f"https://app.hockeyweerelt.nl/"
        f"poules/{poule_id}/teams/{team_id}"
    )

    print("")
    print("=" * 80)
    print(f"TEAM {team_id}")
    print("=" * 80)
    print(f"URL: {url}")

    response = requests.get(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0"
        },
        timeout=30,
    )

    print(f"STATUS: {response.status_code}")
    print(
        f"CONTENT-TYPE: "
        f"{response.headers.get('content-type')}"
    )

    print("")
    print("RESPONSE:")
    print(response.text[:5000])
    print("")

    return response.text


def main():

    Path("public").mkdir(
        parents=True,
        exist_ok=True
    )

    for team in TEAMS:

        fetch_team(
            team["team_id"],
            team["poule_id"]
        )

    print("Finished")


if __name__ == "__main__":
    main()
