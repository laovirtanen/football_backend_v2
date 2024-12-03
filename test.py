# test.py

import asyncio
import httpx
import logging
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models import Base
from app.database import get_db
from app.routers.ingestion.ingest_fixtures_data import fetch_and_store_match_statistics

# Replace with your actual database URL and API key
DATABASE_URL = "postgresql+asyncpg://lauri:toblerone@localhost:5432/postgres"
API_FOOTBALL_KEY = "778535c0339ceea93f4d00e2e3b10f25"

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

async def main():
    engine = create_async_engine(DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    # Ensure that the database schema is up to date
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        headers = {
            'x-apisports-key': API_FOOTBALL_KEY,
            'Accept': 'application/json'
        }
        async with httpx.AsyncClient() as client:
            # Replace with the fixture ID you want to test
            fixture_id = 1208133
            logger.info(f"Testing fetch_and_store_match_statistics for fixture ID: {fixture_id}")
            await fetch_and_store_match_statistics(fixture_id, client, session, headers)

if __name__ == "__main__":
    asyncio.run(main())
