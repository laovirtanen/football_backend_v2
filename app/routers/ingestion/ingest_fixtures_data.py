# app/routers/ingestion/ingest_fixtures_data.py

import logging
import os
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
import httpx

from app.database import get_db
from app import models

router = APIRouter(
    prefix="/ingest",
    tags=["ingestion"]
)

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.post("/fixtures_data/", response_model=dict)
async def fetch_and_store_fixtures_data(db: AsyncSession = Depends(get_db)):
    logger.info("Starting the fixtures data ingestion process.")

    if not API_FOOTBALL_KEY:
        logger.error("API_FOOTBALL_KEY environment variable is not set.")
        raise HTTPException(status_code=500, detail="API key not configured.")

    league_id = 2  

    # Fetch the current season for this league
    seasons_result = await db.execute(
        select(models.Season).filter(
            models.Season.league_id == league_id,
            models.Season.current == True
        )
    )
    current_season = seasons_result.scalar_one_or_none()

    if not current_season or not current_season.start_date or not current_season.end_date:
        logger.error("Current season or its start/end dates not found.")
        raise HTTPException(
            status_code=404,
            detail="Current season not found or missing start/end dates."
        )

    # Use the season's start_date and end_date as the date range
    start_date = datetime.combine(current_season.start_date, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_date = datetime.combine(current_season.end_date, datetime.min.time()).replace(tzinfo=timezone.utc)

    headers = {
        'x-apisports-key': API_FOOTBALL_KEY,
        'Accept': 'application/json'
    }

    try:
        async with httpx.AsyncClient() as client:
            fixtures_result = await db.execute(
                select(models.Fixture.fixture_id, models.Fixture.status_short).filter(
                    models.Fixture.date >= start_date,
                    models.Fixture.date <= end_date
                )
            )
            fixture_rows = fixtures_result.fetchall()

            if not fixture_rows:
                logger.info("No fixtures found within the specified date range.")
                return {"message": "No fixtures found within the specified date range."}

            data_processed = 0

            for fixture_id, status_short in fixture_rows:
                logger.info(f"Processing fixture ID: {fixture_id}")

                await fetch_and_store_prediction_for_fixture(fixture_id, client, db, headers)
                await fetch_and_store_odds_for_fixture(fixture_id, client, db, headers)

                if status_short in ['FT', 'AET', 'PEN', 'AWD', 'WO']:
                    await fetch_and_store_match_statistics(fixture_id, client, db, headers)
                    await fetch_and_store_match_events(fixture_id, client, db, headers)

                data_processed += 1

            logger.info(f"Finished fetching and storing data. Total fixtures processed: {data_processed}")
            return {"message": "Fixtures data fetched and stored successfully", "processed": data_processed}

    except Exception as e:
        await db.rollback()
        logger.error(f"An unexpected error occurred during fixtures data ingestion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def fetch_and_store_prediction_for_fixture(fixture_id, client, db, headers):
    try:
        params = {'fixture': fixture_id}
        response = await client.get("https://v3.football.api-sports.io/predictions", headers=headers, params=params)

        if response.status_code != 200:
            logger.error(f"Failed to fetch prediction for fixture {fixture_id}: {response.text}")
            return

        data = response.json()
        predictions_response = data.get("response", [])

        if not predictions_response:
            logger.info(f"No prediction available for fixture {fixture_id}.")
            return

        prediction_data = predictions_response[0]
        predictions = prediction_data.get("predictions", {})
        winner = predictions.get("winner", {})
        win_or_draw = predictions.get("win_or_draw")
        under_over = predictions.get("under_over")
        goals = predictions.get("goals", {})
        advice = predictions.get("advice")
        percent = predictions.get("percent", {})
        comparison = prediction_data.get("comparison", {})

        existing_prediction_result = await db.execute(
            select(models.Prediction).where(models.Prediction.fixture_id == fixture_id)
        )
        existing_prediction = existing_prediction_result.scalars().first()

        if existing_prediction:
            existing_prediction.winner_team_id = winner.get("id")
            existing_prediction.win_or_draw = win_or_draw
            existing_prediction.under_over = under_over
            existing_prediction.goals_home = goals.get("home")
            existing_prediction.goals_away = goals.get("away")
            existing_prediction.advice = advice
            existing_prediction.percent_home = percent.get("home")
            existing_prediction.percent_draw = percent.get("draw")
            existing_prediction.percent_away = percent.get("away")
            existing_prediction.comparison = comparison
        else:
            prediction = models.Prediction(
                fixture_id=fixture_id,
                winner_team_id=winner.get("id"),
                win_or_draw=win_or_draw,
                under_over=under_over,
                goals_home=goals.get("home"),
                goals_away=goals.get("away"),
                advice=advice,
                percent_home=percent.get("home"),
                percent_draw=percent.get("draw"),
                percent_away=percent.get("away"),
                comparison=comparison
            )
            db.add(prediction)

        await db.commit()
        logger.info(f"Stored prediction for fixture {fixture_id}.")

    except IntegrityError as ie:
        await db.rollback()
        logger.error(f"Integrity error while storing prediction for fixture {fixture_id}: {ie}", exc_info=True)
    except Exception as e:
        await db.rollback()
        logger.error(f"Error fetching prediction for fixture {fixture_id}: {e}", exc_info=True)


async def fetch_and_store_odds_for_fixture(fixture_id, client, db, headers):
    try:
        params = {'fixture': fixture_id}
        response = await client.get("https://v3.football.api-sports.io/odds", headers=headers, params=params)

        if response.status_code != 200:
            logger.error(f"Failed to fetch odds for fixture {fixture_id}: {response.text}")
            return

        data = response.json()
        odds_response = data.get("response", [])

        if not odds_response:
            logger.info(f"No odds available for fixture {fixture_id}.")
            return

        await db.execute(
            delete(models.FixtureOdds).where(models.FixtureOdds.fixture_id == fixture_id)
        )
        await db.commit()

        for odds_data in odds_response:
            fixture_info = odds_data.get("fixture", {})
            fixture_id_resp = fixture_info.get("id")
            if fixture_id_resp != fixture_id:
                continue

            update_time_str = odds_data.get("update")
            update_time = datetime.fromisoformat(update_time_str.replace('Z', '+00:00'))

            fixture_odds = models.FixtureOdds(
                fixture_id=fixture_id,
                update_time=update_time
            )
            db.add(fixture_odds)
            await db.commit()
            await db.refresh(fixture_odds)

            for bookmaker_data in odds_data.get("bookmakers", []):
                bookmaker_id = bookmaker_data.get("id")
                bookmaker_name = bookmaker_data.get("name")

                bookmaker_result = await db.execute(
                    select(models.Bookmaker).where(models.Bookmaker.id == bookmaker_id)
                )
                bookmaker = bookmaker_result.scalars().first()

                if not bookmaker:
                    bookmaker = models.Bookmaker(id=bookmaker_id, name=bookmaker_name)
                    db.add(bookmaker)
                    try:
                        await db.commit()
                    except IntegrityError:
                        await db.rollback()
                        bookmaker = await db.get(models.Bookmaker, bookmaker_id)

                fixture_bookmaker = models.FixtureBookmaker(
                    fixture_odds_id=fixture_odds.id,
                    bookmaker_id=bookmaker.id
                )
                db.add(fixture_bookmaker)
                await db.commit()
                await db.refresh(fixture_bookmaker)

                for bet_data in bookmaker_data.get("bets", []):
                    bet_type_id = bet_data.get("id")
                    bet_type_name = bet_data.get("name")

                    bet_type = await db.get(models.BetType, bet_type_id)
                    if not bet_type:
                        bet_type = models.BetType(id=bet_type_id, name=bet_type_name)
                        db.add(bet_type)
                        try:
                            await db.commit()
                        except IntegrityError:
                            await db.rollback()
                            bet_type = await db.get(models.BetType, bet_type_id)

                    bet = models.Bet(
                        fixture_bookmaker_id=fixture_bookmaker.id,
                        bet_type_id=bet_type.id
                    )
                    db.add(bet)
                    await db.commit()
                    await db.refresh(bet)

                    for value_data in bet_data.get("values", []):
                        value = str(value_data.get("value"))
                        odd = value_data.get("odd")

                        odd_value = models.OddValue(
                            bet_id=bet.id,
                            value=value,
                            odd=odd
                        )
                        db.add(odd_value)

        await db.commit()
        logger.info(f"Stored odds for fixture {fixture_id}.")

    except IntegrityError as ie:
        await db.rollback()
        logger.error(f"IntegrityError while handling odds for fixture {fixture_id}: {ie}", exc_info=True)
    except Exception as e:
        await db.rollback()
        logger.error(f"Error fetching odds for fixture {fixture_id}: {e}", exc_info=True)


async def fetch_and_store_match_statistics(fixture_id, client, db, headers):
    try:
        params = {'fixture': fixture_id}
        response = await client.get(
            "https://v3.football.api-sports.io/fixtures/statistics",
            headers=headers,
            params=params
        )

        if response.status_code != 200:
            logger.error(f"Failed to fetch statistics for fixture {fixture_id}: {response.text}")
            return

        data = response.json()
        statistics_response = data.get("response", [])

        if not statistics_response:
            logger.info(f"No statistics available for fixture {fixture_id}.")
            return

        await db.execute(
            delete(models.MatchStatistics).where(models.MatchStatistics.fixture_id == fixture_id)
        )
        await db.commit()

        for stat in statistics_response:
            team_id = stat.get("team", {}).get("id")
            statistics = stat.get("statistics", [])
            match_statistics = models.MatchStatistics(
                fixture_id=fixture_id,
                team_id=team_id,
                statistics=statistics
            )
            db.add(match_statistics)

        await db.commit()
        logger.info(f"Stored statistics for fixture {fixture_id}.")

    except Exception as e:
        await db.rollback()
        logger.error(f"Error fetching statistics for fixture {fixture_id}: {e}", exc_info=True)


async def fetch_and_store_match_events(fixture_id, client, db, headers):
    try:
        params = {'fixture': fixture_id}
        response = await client.get(
            "https://v3.football.api-sports.io/fixtures/events",
            headers=headers,
            params=params
        )

        if response.status_code != 200:
            logger.error(f"Failed to fetch events for fixture {fixture_id}: {response.text}")
            return

        data = response.json()
        events_response = data.get("response", [])

        if not events_response:
            logger.info(f"No events available for fixture {fixture_id}.")
            return

        await db.execute(
            delete(models.MatchEvent).where(models.MatchEvent.fixture_id == fixture_id)
        )
        await db.commit()

        try:
            for event_data in events_response:
                event = models.MatchEvent(
                    fixture_id=fixture_id,
                    minute=event_data['time']['elapsed'],
                    team_id=event_data['team']['id'],
                    player_id=event_data.get('player', {}).get('id'),
                    player_name=event_data.get('player', {}).get('name'),
                    type=event_data['type'],
                    detail=event_data['detail'],
                    comments=event_data.get('comments')
                )
                db.add(event)

            await db.commit()
            logger.info(f"Stored events for {fixture_id}.")
        except IntegrityError as ie:
            await db.rollback()
            logger.error(f"IntegrityError storing events for fixture {fixture_id}: {ie}", exc_info=True)
        except Exception as e:
            await db.rollback()
            logger.error(f"Error fetching events for fixture {fixture_id}: {e}", exc_info=True)

    except Exception as e:
        await db.rollback()
        logger.error(f"Error fetching events for fixture {fixture_id}: {e}", exc_info=True)
