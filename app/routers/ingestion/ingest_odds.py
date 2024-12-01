# app/routers/ingestion/odds.py

import logging
import os
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import httpx

from app.database import get_db
from app import models

router = APIRouter(
    prefix="/odds",
    tags=["odds"]
)

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.post("/", response_model=dict)
async def fetch_and_store_odds(db: AsyncSession = Depends(get_db)):
    logger.info("Starting the odds ingestion process.")
    try:
        if not API_FOOTBALL_KEY:
            logger.error("API_FOOTBALL_KEY environment variable is not set.")
            raise HTTPException(status_code=500, detail="API key not configured.")

        headers = {
            'x-apisports-key': API_FOOTBALL_KEY,
            'Accept': 'application/json'
        }

        async with httpx.AsyncClient() as client:
            # Fetch fixtures within a certain date range (modify as needed)
            start_date = datetime.utcnow()
            end_date = start_date + timedelta(days=14)
            fixtures_result = await db.execute(
                select(models.Fixture.fixture_id).filter(
                    models.Fixture.date >= start_date,
                    models.Fixture.date <= end_date
                )
            )
            fixture_ids = [fixture_id for (fixture_id,) in fixtures_result.fetchall()]

            if not fixture_ids:
                logger.info("No fixtures found within the specified date range.")
                return {"message": "No fixtures found within the specified date range."}

            odds_processed = 0

            for fixture_id in fixture_ids:
                logger.info(f"Fetching odds for fixture ID: {fixture_id}")
                params = {
                    'fixture': fixture_id
                }

                response = await client.get(
                    "https://v3.football.api-sports.io/odds",
                    headers=headers,
                    params=params
                )

                if response.status_code != 200:
                    logger.error(f"Failed to fetch odds for fixture {fixture_id}: {response.text}")
                    continue

                data = response.json()
                odds_response = data.get("response", [])

                if not odds_response:
                    logger.info(f"No odds available for fixture {fixture_id}.")
                    continue

                # Delete existing odds for this fixture
                await db.execute(
                    delete(models.FixtureOdds).where(models.FixtureOdds.fixture_id == fixture_id)
                )
                await db.commit()

                # Process odds data
                for odds_data in odds_response:
                    fixture_info = odds_data.get("fixture", {})
                    fixture_id_response = fixture_info.get("id")

                    if fixture_id_response != fixture_id:
                        continue

                    # Extract update time
                    update_time_str = odds_data.get("update")
                    update_time = datetime.fromisoformat(update_time_str.replace('Z', '+00:00'))

                    # Create FixtureOdds
                    fixture_odds = models.FixtureOdds(
                        fixture_id=fixture_id,
                        update_time=update_time
                    )
                    db.add(fixture_odds)
                    await db.commit()
                    await db.refresh(fixture_odds)

                    # Process bookmakers
                    for bookmaker_data in odds_data.get("bookmakers", []):
                        bookmaker_id = bookmaker_data.get("id")
                        bookmaker_name = bookmaker_data.get("name")

                        # Get or create Bookmaker
                        bookmaker = await db.get(models.Bookmaker, bookmaker_id)
                        if not bookmaker:
                            bookmaker = models.Bookmaker(
                                id=bookmaker_id,
                                name=bookmaker_name
                            )
                            db.add(bookmaker)
                            await db.commit()
                            await db.refresh(bookmaker)

                        fixture_bookmaker = models.FixtureBookmaker(
                            fixture_odds_id=fixture_odds.id,
                            bookmaker_id=bookmaker.id
                        )
                        db.add(fixture_bookmaker)
                        await db.commit()
                        await db.refresh(fixture_bookmaker)

                        # Process bets
                        for bet_data in bookmaker_data.get("bets", []):
                            bet_type_id = bet_data.get("id")
                            bet_type_name = bet_data.get("name")

                            # Get or create BetType
                            bet_type = await db.get(models.BetType, bet_type_id)
                            if not bet_type:
                                bet_type = models.BetType(
                                    id=bet_type_id,
                                    name=bet_type_name
                                )
                                db.add(bet_type)
                                await db.commit()
                                await db.refresh(bet_type)

                            bet = models.Bet(
                                fixture_bookmaker_id=fixture_bookmaker.id,
                                bet_type_id=bet_type.id
                            )
                            db.add(bet)
                            await db.commit()
                            await db.refresh(bet)

                            # Process odd values
                            for value_data in bet_data.get("values", []):
                                value = str(value_data.get("value"))
                                odd = value_data.get("odd")

                                odd_value = models.OddValue(
                                    bet_id=bet.id,
                                    value=value,
                                    odd=odd
                                )
                                db.add(odd_value)

                    # Commit all odds for this fixture
                    await db.commit()
                    odds_processed += 1

            logger.info(f"Finished fetching and storing odds. Total odds processed: {odds_processed}")
            return {"message": "Odds fetched and stored successfully", "processed": odds_processed}

    except Exception as e:
        logger.error(f"An error occurred during odds ingestion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
