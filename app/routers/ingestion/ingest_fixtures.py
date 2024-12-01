# app/routers/ingestion/ingest_fixtures.py

import logging
import os
import json
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

# Create a logger for this module
logger = logging.getLogger(__name__)

# Fetch the API key from environment variables
API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")

@router.post("/", response_model=dict)
async def fetch_and_store_fixtures(db: AsyncSession = Depends(get_db)):
    logger.info("Starting the fixtures ingestion process.")
    try:
        # Validate API key
        if not API_FOOTBALL_KEY:
            logger.error("API_FOOTBALL_KEY environment variable is not set.")
            raise HTTPException(status_code=500, detail="API key not configured.")

        # Fetch current seasons
        seasons_query = select(models.Season).filter(models.Season.current == True)
        seasons_result = await db.execute(seasons_query)
        seasons = seasons_result.scalars().all()

        if not seasons:
            logger.info("No current seasons found.")
            return {"message": "No current seasons found."}
        else:
            logger.info(f"Found {len(seasons)} current seasons.")

        headers = {
            'x-apisports-key': API_FOOTBALL_KEY,
            'Accept': 'application/json'  # Ensures JSON response
        }

        fixtures_processed = 0  # Counter for processed fixtures

        async with httpx.AsyncClient() as client:
            for season in seasons:
                league_id = season.league_id
                season_year = season.year

                logger.info(f"Fetching fixtures for league {league_id} and season {season_year}.")

                url = "https://v3.football.api-sports.io/fixtures"
                params = {
                    'league': league_id,
                    'season': season_year
                }

                response = await client.get(url, headers=headers, params=params)
                logger.debug(f"API response status: {response.status_code} for league {league_id}, season {season_year}")

                if response.status_code != 200:
                    logger.error(f"API Error for league {league_id}, season {season_year}: {response.status_code} - {response.text}")
                    continue  # Move to next league

                try:
                    data = response.json()
                    logger.debug(f"API Response Data for league {league_id}, season {season_year}: {json.dumps(data, indent=2)}")
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decoding error for league {league_id}, season {season_year}: {e}")
                    continue  # Skip this league

                fixtures_data = data.get("response", [])
                if not fixtures_data:
                    logger.warning(f"No fixtures found for league {league_id} and season {season_year}.")
                    continue  # No fixtures to process

                logger.info(f"Fetched {len(fixtures_data)} fixtures for league {league_id}, season {season_year}.")

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
                        event_date = None
                        if event_date_str:
                            try:
                                aware_date = datetime.fromisoformat(event_date_str.replace('Z', '+00:00'))
                                event_date = aware_date.astimezone(timezone.utc)
                            except Exception as e:
                                logger.error(f"Date parsing error for fixture {fixture_info.get('id')}: {e}", exc_info=True)
                                # Keep event_date as None if parsing fails

                        # Ensure we have necessary team IDs
                        home_team_id = teams_info.get("home", {}).get("id")
                        away_team_id = teams_info.get("away", {}).get("id")

                        if not home_team_id or not away_team_id:
                            logger.warning(f"Skipping fixture {fixture_info.get('id')} due to missing team IDs.")
                            continue

                        # Check if the teams exist in the database
                        home_team_query = select(models.Team).filter(
                            models.Team.team_id == home_team_id,
                            models.Team.season_year == season_year
                        )
                        home_team_result = await db.execute(home_team_query)
                        home_team = home_team_result.scalars().one_or_none()

                        away_team_query = select(models.Team).filter(
                            models.Team.team_id == away_team_id,
                            models.Team.season_year == season_year
                        )
                        away_team_result = await db.execute(away_team_query)
                        away_team = away_team_result.scalars().one_or_none()

                        if not home_team or not away_team:
                            logger.warning(f"Home or away team not found in the database for fixture {fixture_info.get('id')}.")
                            continue

                        venue_id = venue_info.get("id")
                        venue = None
                        if venue_id:
                            venue_query = select(models.Venue).filter(models.Venue.id == venue_id)
                            venue_result = await db.execute(venue_query)
                            venue = venue_result.scalars().one_or_none()
                            if not venue:
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
                                    venue_query = select(models.Venue).filter(models.Venue.id == venue_id)
                                    venue_result = await db.execute(venue_query)
                                    venue = venue_result.scalars().one_or_none()

                        # Ensure fixture ID is present
                        fixture_id = fixture_info.get("id")
                        if not fixture_id:
                            logger.warning("No fixture ID found in API data; skipping this fixture.")
                            continue

                        # Determine if the fixture is final
                        status_short = fixture_info.get("status", {}).get("short")
                        final_statuses = {"FT", "AET", "PEN", "AWD", "WO"}
                        is_final = status_short in final_statuses

                        # Check if fixture already exists
                        existing_fixture_query = select(models.Fixture).filter(models.Fixture.fixture_id == fixture_id)
                        existing_fixture_result = await db.execute(existing_fixture_query)
                        existing_fixture = existing_fixture_result.scalars().one_or_none()

                        if not existing_fixture:
                            # Create a new Fixture instance
                            fixture = models.Fixture(
                                fixture_id=fixture_id,
                                referee=fixture_info.get("referee"),
                                timezone=fixture_info.get("timezone"),
                                date=event_date,
                                timestamp=fixture_info.get("timestamp"),
                                venue_id=venue.id if venue else None,
                                status_long=fixture_info.get("status", {}).get("long"),
                                status_short=status_short,
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
                                score_penalty_away=score_info.get("penalty", {}).get("away"),
                                is_final=is_final  # Use the column from the model
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
                                existing_fixture_result = await db.execute(existing_fixture_query)
                                existing_fixture = existing_fixture_result.scalars().one_or_none()
                                if existing_fixture:
                                    logger.info(f"Fixture ID {fixture_id} fetched from the database.")
                                else:
                                    logger.error(f"Failed to fetch fixture ID {fixture_id} after IntegrityError.")
                                    continue  # Skip this fixture
                        else:
                            # Update existing fixture if needed
                            fixture_changed = False
                            new_status_short = fixture_info.get("status", {}).get("short")
                            if existing_fixture.status_short != new_status_short:
                                existing_fixture.status_short = new_status_short
                                fixture_changed = True
                                existing_fixture.is_final = new_status_short in final_statuses

                            # Update goals if changed
                            new_goals_home = goals_info.get("home")
                            new_goals_away = goals_info.get("away")
                            if existing_fixture.goals_home != new_goals_home:
                                existing_fixture.goals_home = new_goals_home
                                fixture_changed = True
                            if existing_fixture.goals_away != new_goals_away:
                                existing_fixture.goals_away = new_goals_away
                                fixture_changed = True

                            # Update half-time, full-time scores if changed
                            new_score_halftime_home = score_info.get("halftime", {}).get("home")
                            new_score_halftime_away = score_info.get("halftime", {}).get("away")
                            new_score_fulltime_home = score_info.get("fulltime", {}).get("home")
                            new_score_fulltime_away = score_info.get("fulltime", {}).get("away")

                            if existing_fixture.score_halftime_home != new_score_halftime_home:
                                existing_fixture.score_halftime_home = new_score_halftime_home
                                fixture_changed = True
                            if existing_fixture.score_halftime_away != new_score_halftime_away:
                                existing_fixture.score_halftime_away = new_score_halftime_away
                                fixture_changed = True
                            if existing_fixture.score_fulltime_home != new_score_fulltime_home:
                                existing_fixture.score_fulltime_home = new_score_fulltime_home
                                fixture_changed = True
                            if existing_fixture.score_fulltime_away != new_score_fulltime_away:
                                existing_fixture.score_fulltime_away = new_score_fulltime_away
                                fixture_changed = True

                            # Update extra-time and penalty scores if changed
                            new_score_extratime_home = score_info.get("extratime", {}).get("home")
                            new_score_extratime_away = score_info.get("extratime", {}).get("away")
                            new_score_penalty_home = score_info.get("penalty", {}).get("home")
                            new_score_penalty_away = score_info.get("penalty", {}).get("away")

                            if existing_fixture.score_extratime_home != new_score_extratime_home:
                                existing_fixture.score_extratime_home = new_score_extratime_home
                                fixture_changed = True
                            if existing_fixture.score_extratime_away != new_score_extratime_away:
                                existing_fixture.score_extratime_away = new_score_extratime_away
                                fixture_changed = True
                            if existing_fixture.score_penalty_home != new_score_penalty_home:
                                existing_fixture.score_penalty_home = new_score_penalty_home
                                fixture_changed = True
                            if existing_fixture.score_penalty_away != new_score_penalty_away:
                                existing_fixture.score_penalty_away = new_score_penalty_away
                                fixture_changed = True

                            if fixture_changed:
                                await db.commit()
                                logger.info(f"Fixture ID {existing_fixture.fixture_id} updated in the database.")
                    except Exception as e:
                        logger.error(f"Error processing fixture: {e}", exc_info=True)
                        await db.rollback()  # Ensure the session is clean
                        continue  # Proceed with next fixture

        logger.info(f"Finished fetching and storing fixtures. Total fixtures processed: {fixtures_processed}")
        return {"message": "Fixtures fetched and stored successfully", "processed": fixtures_processed}
    except Exception as e:
        logger.error(f"An error occurred during fixture ingestion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
