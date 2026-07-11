import asyncio

from faker import Faker
from sqlalchemy import delete

from app.db import SessionLocal
from app.models import Item

fake = Faker()


async def main() -> None:
    async with SessionLocal() as session:
        await session.execute(delete(Item))
        session.add_all(
            Item(
                title=fake.catch_phrase(),
                description=fake.sentence(),
                completed=fake.boolean(),
            )
            for _ in range(5)
        )
        await session.commit()
    print("Seeded 5 items.")


if __name__ == "__main__":
    asyncio.run(main())
