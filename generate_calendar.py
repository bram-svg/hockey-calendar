import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
 
import requests
from dateutil import parser as date_parser
from icalendar import Calendar, Event
 
 
TEAMS = [
{
"team_id": 42637,
"poule_id": 183108,
"label": "Team 42637",
},
{
"team_id": 6344,
"poule_id": 182127,
"label": "Team 6344",
},
{
"team_id": 46147,
"poule_id": 182243,
"label": "Team 46147",
},
{
"team_id": 39358,
"poule_id": 182090,
"label": "Team 39358",
},
]
 
API_URL = (
"https://app.hockeyweerelt.nl/poules/"
"{poule_id}/teams/{team_id}"
)
 
OUTPUT_FILE = Path("docs/hockey.ics")
TIMEOUT = 30
 
HEADERS = {
"Accept": "application/json",
"User-Agent": (
"hockey-calendar/1.0 "
"(personal calendar generator)"
),
}
 
 
def first_value(data: dict, names: list[str], default=None):
"""Return the first present and non-empty field."""
for name in names:
value = data.get(name)
if value not in (None, ""):
return value
return default
 
 
def walk_for_matches(value: Any) -> list"""
Recursively locate match-like dictionaries.
 
The API is not formally documented, so this deliberately accepts
several possible response structures.
"""
matches = []
 
if isinstance(value, list):
for item in value:
matches.extend(walk_for_matches(item))
return matches
 
if not isinstance(value, dict):
return matches
 
keys = {str(key).lower() for key in value}
 
home_indicators = {
"home_team",
"hometeam",
"home_team_name",
"homeclub",
"home",
"team_home",
"home_name",
}
 
away_indicators = {
"away_team",
"awayteam",
"away_team_name",
"awayclub",
"away",
"team_away",
"away_name",
}
 
date_indicators = {
"date",
"datetime",
"start",
"start_time",
"startdate",
"scheduled_at",
"match_date",
"date_time",
}
 
if (
keys.intersection(home_indicators)
and keys.intersection(away_indicators)
and keys.intersection(date_indicators)
):
matches.append(value)
return matches
 
for nested_value in value.values():
matches.extend(walk_for_matches(nested_value))
 
return matches
 
 
def team_name(value: Any) -> str | None:
"""Extract a readable team name from a string or nested object."""
if isinstance(value, str):
return value.strip()
 
if isinstance(value, dict):
result = first_value(
value,
[
"name",
"team_name",
"teamName",
"title",
"short_name",
"shortName",
],
)
if result:
return str(result).strip()
 
return None
 
 
def get_side(match: dict, side: str) -> str:
field_options = {
"home": [
"home_team",
"homeTeam",
"hometeam",
"home_team_name",
"homeTeamName",
"homeclub",
"homeClub",
"team_home",
"home",
"home_name",
],
"away": [
"away_team",
"awayTeam",
"awayteam",
"away_team_name",
"awayTeamName",
"awayclub",
"awayClub",
"team_away",
"away",
"away_name",
],
}
 
for field in field_options[side]:
if field in match:
name = team_name(match[field])
if name:
return name
 
return "Onbekend team"
 
 
def parse_match_datetime(match: dict) -> datetime | None:
combined = first_value(
match,
[
"datetime",
"dateTime",
"start",
"start_time",
"startTime",
"startdate",
"startDate",
"scheduled_at",
"scheduledAt",
"match_date_time",
"matchDateTime",
],
)
 
if combined:
try:
parsed = date_parser.parse(str(combined))
if parsed.tzinfo is None:
parsed = parsed.replace(
tzinfo=date_parser.parse(
"2026-01-01T12:00:00+01:00"
).tzinfo
)
return parsed
except (ValueError, TypeError):
pass
 
date_value = first_value(
match,
[
"date",
"match_date",
"matchDate",
"play_date",
"playDate",
],
)
 
time_value = first_value(
match,
[
"time",
"match_time",
"matchTime",
"play_time",
"playTime",
],
"00:00",
)
 
if not date_value:
return None
 
try:
parsed = date_parser.parse(f"{date_value} {time_value}")
if parsed.tzinfo is None:
# Dutch local time. The calendar itself specifies Europe/Amsterdam.
parsed = parsed.replace(
tzinfo=date_parser.parse(
"2026-01-01T12:00:00+01:00"
).tzinfo
)
return parsed
except (ValueError, TypeError):
return None
 
 
def get_location(match: dict) -> str:
value = first_value(
match,
[
"location",
"venue",
"address",
"accommodation",
"accommodation_name",
"accommodationName",
"club_address",
"clubAddress",
],
"",
)
 
if isinstance(value, dict):
parts = [
first_value(value, ["name", "title"], ""),
first_value(value, ["address", "street"], ""),
first_value(value, ["city", "place"], ""),
]
return ", ".join(str(part) for part in parts if part)
 
return str(value).strip()
 
 
def get_match_id(match: dict, fallback: str) -> str:
value = first_value(
match,
[
"id",
"match_id",
"matchId",
"game_id",
"gameId",
"wedstrijd_id",
"wedstrijdId",
],
)
 
if value:
return str(value)
 
return hashlib.sha256(fallback.encode("utf-8")).hexdigest()[:24]
 
 
def fetch_matches(team: dict) -> list[dict]:
url = API_URL.format(
team_id=team["team_id"],
poule_id=team["poule_id"],
)
 
print(f"Fetching {team['label']}: {url}")
 
response = requests.get(
url,
headers=HEADERS,
timeout=TIMEOUT,
)
response.raise_for_status()
 
payload = response.json()
matches = walk_for_matches(payload)
 
print(f" Found {len(matches)} candidate matches")
 
for match in matches:
match["_source_team_id"] = team["team_id"]
match["_source_poule_id"] = team["poule_id"]
match["_source_label"] = team["label"]
 
return matches
 
 
def create_calendar(matches: list[dict]) -> Calendar:
calendar = Calendar()
calendar.add("prodid", "-//Hockey.nl Team Calendar//NL")
calendar.add("version", "2.0")
calendar.add("calscale", "GREGORIAN")
calendar.add("method", "PUBLISH")
calendar.add("x-wr-calname", "Hockeywedstrijden")
calendar.add("x-wr-timezone", "Europe/Amsterdam")
calendar.add(
"x-wr-caldesc",
"Automatisch bijgewerkt wedstrijdschema van Hockey.nl",
)
 
seen = set()
 
for match in matches:
start = parse_match_datetime(match)
 
if start is None:
print(f"Skipping match without usable date: {match}")
continue
 
home = get_side(match, "home")
away = get_side(match, "away")
location = get_location(match)
 
fallback_key = (
f"{home}|{away}|{start.isoformat()}|{location}"
)
match_id = get_match_id(match, fallback_key)
uid = f"{match_id}@hockey-calendar.github.io"
 
if uid in seen:
continue
 
seen.add(uid)
 
end_value = first_value(
match,
[
"end",
"end_time",
"endTime",
"end_datetime",
"endDateTime",
],
)
 
if end_value:
try:
end = date_parser.parse(str(end_value))
if end.tzinfo is None:
end = start + timedelta(hours=2)
except (ValueError, TypeError):
end = start + timedelta(hours=2)
else:
end = start + timedelta(hours=2)
 
status = str(
first_value(match, ["status", "match_status"], "")
).lower()
 
event = Event()
event.add("uid", uid)
event.add("summary", f"{home} - {away}")
event.add("dtstart", start)
event.add("dtend", end)
event.add("dtstamp", datetime.now(timezone.utc))
event.add("last-modified", datetime.now(timezone.utc))
event.add("location", location)
 
description_lines = [
"Automatisch overgenomen uit Hockey.nl.",
f"Team-ID: {match['_source_team_id']}",
f"Poule-ID: {match['_source_poule_id']}",
]
 
event.add("description", "\n".join(description_lines))
 
if status in {"cancelled", "canceled", "afgelast"}:
event.add("status", "CANCELLED")
else:
event.add("status", "CONFIRMED")
 
calendar.add_component(event)
 
return calendar
 
 
def main():
all_matches = []
errors = []
 
for team in TEAMS:
try:
all_matches.extend(fetch_matches(team))
except Exception as exc:
message = f"{team['label']}: {exc}"
errors.append(message)
print(f"ERROR: {message}")
 
if not all_matches:
raise RuntimeError(
"Geen wedstrijden gevonden. "
"Mogelijk is de API-structuur gewijzigd. "
f"Fouten: {'; '.join(errors)}"
)
 
calendar = create_calendar(all_matches)
 
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE.write_bytes(calendar.to_ical())
 
print(
f"Calendar written to {OUTPUT_FILE} "
f"with {len(calendar.subcomponents)} events"
)
 
if errors:
print("Some teams could not be retrieved:")
for error in errors:
print(f" - {error}")
 
 
if __name__ == "__main__":
main()
