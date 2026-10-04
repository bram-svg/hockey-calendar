import asyncio

from hockeyweerelt import Api


async def main():
    async with await Api.create() as api:

        matches = await api.get_team_matches(
            42637,
            183108,
        )

        print(f"Aantal wedstrijden: {len(matches)}")

        if matches:
            print(matches[0])


asyncio.run(main())
