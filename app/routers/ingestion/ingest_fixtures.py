import logging
import os
import json
import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
import httpx

from app.database import get_db
from app import models

router = APIRouter(
    prefix="/fixtures",
    tags=["fixtures"]
)

# Fetch the API key from environment variables
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.post("/", response_model=dict)
async def fetch_and_store_fixtures(db: AsyncSession = Depends(get_db)):
    logger.info("Starting the fixtures ingestion process.")
    try:
        # Validate API key
        if not API_FOOTBALL_KEY:
            logger.error("API_FOOTBALL_KEY environment variable is not set.")
            raise HTTPException(status_code=500, detail="API key not configured.")

        # Fetch current seasons
        seasons_result = await db.execute(
            select(models.Season).filter(models.Season.current == True)
        )
        seasons = seasons_result.scalars().all()

        if not seasons:
            logger.info("No current seasons found.")
            return {"message": "No current seasons found."}
        else:
            logger.info(f"Found {len(seasons)} current seasons.")

        headers = {
            'x-apisports-key': API_FOOTBALL_KEY,
            # Uncomment the following line if the API requires 'x-rapidapi-host'
            # 'x-rapidapi-host': 'v3.football.api-sports.io'
            'Accept': 'application/json'  # Ensures JSON response
        }

        fixtures_processed = 0  # Counter for processed fixtures

        async with httpx.AsyncClient() as client:
            for season in seasons:
                season_year = season.year
                league_id = season.league_id

                logger.info(f"Fetching fixtures for league {league_id} and season {season_year}.")

                url = "https://v3.football.api-sports.io/fixtures"

                # Parameters aligned with Postman (includes pagination if supported)
                params = {
                    'league': league_id,
                    'season': season_year,
                    # Add 'page': page_number if pagination is required
                }

                try:
                    response = await client.get(url, headers=headers, params=params)
                    logger.debug(f"API response status: {response.status_code}")

                    if response.status_code != 200:
                        logger.error(f"API Error: {response.status_code} - {response.text}")
                        continue  # Move to next league

                    try:
                        data = response.json()
                        logger.debug(f"API Response Data: {json.dumps(data, indent=2)}")
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON decoding error: {e}")
                        continue  # Skip this league

                    fixtures_data = data.get("response", [])
                    if not fixtures_data:
                        logger.warning(f"No fixtures found for league {league_id} and season {season_year}.")
                        continue  # No fixtures to process

                    logger.info(f"Fetched {len(fixtures_data)} fixtures for league {league_id}.")

                    for item in fixtures_data:
                        try:
                            # Extract relevant information from the API response
                            fixture_info = item.get("fixture", {})
                            league_info = item.get("league", {})
                            teams_info = item.get("teams", {})
                            goals_info = item.get("goals", {})
                            score_info = item.get("score", {})
                            venue_info = fixture_info.get("venue", {})

                            # Parse the event date with timezone awareness
                            event_date_str = fixture_info.get("date")
                            try:
                                if event_date_str:
                                    # Parse the ISO formatted date string with timezone
                                    aware_date = datetime.fromisoformat(event_date_str.replace('Z', '+00:00'))
                                    # Ensure it's in UTC
                                    event_date = aware_date.astimezone(timezone.utc)
                                else:
                                    event_date = None
                            except Exception as e:
                                logger.error(f"Date parsing error for fixture {fixture_info.get('id')}: {e}", exc_info=True)
                                event_date = None

                            # Process venue
                            venue_id = venue_info.get("id")
                            venue = None
                            if venue_id:
                                stmt = select(models.Venue).filter(models.Venue.id == venue_id)
                                result = await db.execute(stmt)
                                venue = result.scalar_one_or_none()

                                if not venue:
                                    # Create a new Venue instance
                                    venue = models.Venue(
                                        id=venue_id,
                                        name=venue_info.get("name"),
                                        city=venue_info.get("city")
                                    )
                                    db.add(venue)
                                    try:
                                        await db.commit()
                                        await db.refresh(venue)
                                        logger.info(f"Venue '{venue.name}' added to the database.")
                                    except IntegrityError:
                                        await db.rollback()
                                        logger.warning(f"Venue ID {venue_id} already exists. Fetching from the database.")
                                        stmt = select(models.Venue).filter(models.Venue.id == venue_id)
                                        result = await db.execute(stmt)
                                        venue = result.scalar_one_or_none()
                                        if venue:
                                            logger.info(f"Venue '{venue.name}' fetched from the database.")
                                        else:
                                            logger.error(f"Failed to fetch venue ID {venue_id} after IntegrityError.")
                                            continue  # Skip this fixture
                                else:
                                    logger.info(f"Venue '{venue.name}' already exists in the database.")
                            else:
                                logger.warning("Venue ID is missing.")
                                continue  # Skip this fixture

                            # Process home team
                            home_team_info = teams_info.get("home", {})
                            home_team_id = home_team_info.get("id")
                            if home_team_id:
                                stmt = select(models.Team).filter(
                                    models.Team.team_id == home_team_id,
                                    models.Team.season_year == season_year
                                )
                                result = await db.execute(stmt)
                                home_team = result.scalar_one_or_none()

                                if not home_team:
                                    logger.warning(f"Home team ID {home_team_id} not found in database.")
                                    continue  # Skip this fixture
                            else:
                                logger.warning("Home team ID is missing.")
                                continue  # Skip this fixture

                            # Process away team
                            away_team_info = teams_info.get("away", {})
                            away_team_id = away_team_info.get("id")
                            if away_team_id:
                                stmt = select(models.Team).filter(
                                    models.Team.team_id == away_team_id,
                                    models.Team.season_year == season_year
                                )
                                result = await db.execute(stmt)
                                away_team = result.scalar_one_or_none()

                                if not away_team:
                                    logger.warning(f"Away team ID {away_team_id} not found in database.")
                                    continue  # Skip this fixture
                            else:
                                logger.warning("Away team ID is missing.")
                                continue  # Skip this fixture

                            # Check if fixture already exists
                            fixture_id = fixture_info.get("id")
                            existing_fixture_stmt = select(models.Fixture).filter(models.Fixture.fixture_id == fixture_id)
                            existing_fixture_result = await db.execute(existing_fixture_stmt)
                            existing_fixture = existing_fixture_result.scalar_one_or_none()

                            if not existing_fixture:
                                # Create a new Fixture instance
                                fixture = models.Fixture(
                                    fixture_id=fixture_id,
                                    referee=fixture_info.get("referee"),
                                    timezone=fixture_info.get("timezone"),
                                    date=event_date,  # TIMESTAMPTZ field
                                    timestamp=fixture_info.get("timestamp"),
                                    venue_id=venue.id if venue else None,
                                    status_long=fixture_info.get("status", {}).get("long"),
                                    status_short=fixture_info.get("status", {}).get("short"),
                                    status_elapsed=fixture_info.get("status", {}).get("elapsed"),
                                    status_extra=str(fixture_info.get("status", {}).get("extra")) if fixture_info.get("status", {}).get("extra") is not None else None,
                                    league_id=league_id,
                                    season_year=season_year,
                                    round=league_info.get("round"),
                                    home_team_id=home_team_id,
                                    away_team_id=away_team_id,
                                    goals_home=goals_info.get("home"),
                                    goals_away=goals_info.get("away"),
                                    score_halftime_home=score_info.get("halftime", {}).get("home"),
                                    score_halftime_away=score_info.get("halftime", {}).get("away"),
                                    score_fulltime_home=score_info.get("fulltime", {}).get("home"),
                                    score_fulltime_away=score_info.get("fulltime", {}).get("away"),
                                    score_extratime_home=score_info.get("extratime", {}).get("home"),
                                    score_extratime_away=score_info.get("extratime", {}).get("away"),
                                    score_penalty_home=score_info.get("penalty", {}).get("home"),
                                    score_penalty_away=score_info.get("penalty", {}).get("away")
                                )
                                db.add(fixture)
                                try:
                                    await db.commit()
                                    await db.refresh(fixture)
                                    fixtures_processed += 1
                                    logger.info(f"Fixture ID {fixture_id} added to the database.")
                                except IntegrityError:
                                    await db.rollback()
                                    logger.warning(f"Fixture ID {fixture_id} already exists. Fetching from the database.")
                                    stmt = select(models.Fixture).filter(models.Fixture.fixture_id == fixture_id)
                                    result = await db.execute(stmt)
                                    fixture = result.scalar_one_or_none()
                                    if fixture:
                                        logger.info(f"Fixture ID {fixture_id} fetched from the database.")
                                    else:
                                        logger.error(f"Failed to fetch fixture ID {fixture_id} after IntegrityError.")
                                        continue  # Skip this fixture
                            else:
                                logger.info(f"Fixture ID {fixture_id} already exists in the database.")
                        except Exception as e:
                            logger.error(f"Error processing fixture: {e}", exc_info=True)
                            await db.rollback()  # Ensure the session is clean
                            continue  # Proceed with next fixture

                except Exception as e:
                    logger.error(f"Error fetching fixtures for league {league_id} and season {season_year}: {e}", exc_info=True)
                    continue  # Move to next league

        logger.info(f"Finished fetching and storing fixtures. Total fixtures processed: {fixtures_processed}")
        return {"message": "Fixtures fetched and stored successfully", "processed": fixtures_processed}
    except Exception as e:
        logger.error(f"An error occurred during fixture ingestion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))