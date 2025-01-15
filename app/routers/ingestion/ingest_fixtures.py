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

logger = logging.getLogger(__name__)

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")

@router.post("/", response_model=dict)
async def fetch_and_store_fixtures(db: AsyncSession = Depends(get_db)):
    logger.info("Starting the fixtures ingestion process.")
    
    # Ensure we handle any unexpected exceptions
    try:
        if not API_FOOTBALL_KEY:
            logger.error("API_FOOTBALL_KEY environment variable is not set.")
            raise HTTPException(status_code=500, detail="API key not configured.")

        seasons_query = select(models.Season).filter(models.Season.current == True)
        seasons_result = await db.execute(seasons_query)
        seasons = seasons_result.scalars().all()

        if not seasons:
            logger.info("No current seasons found.")
            return {"message": "No current seasons found."}

        headers = {
            'x-apisports-key': API_FOOTBALL_KEY,
            'Accept': 'application/json'
        }

        fixtures_processed = 0

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

                if response.status_code != 200:
                    logger.error(f"API Error for league {league_id}, season {season_year}: {response.status_code} - {response.text}")
                    continue

                try:
                    data = response.json()
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decoding error for league {league_id}, season {season_year}: {e}")
                    continue

                fixtures_data = data.get("response", [])
                if not fixtures_data:
                    logger.warning(f"No fixtures found for league {league_id} and season {season_year}.")
                    continue

                logger.info(f"Fetched {len(fixtures_data)} fixtures for league {league_id}, season {season_year}.")

                for item in fixtures_data:
                    fixture_info = item.get("fixture", {})
                    league_info = item.get("league", {})
                    teams_info = item.get("teams", {})
                    goals_info = item.get("goals", {})
                    score_info = item.get("score", {})
                    venue_info = fixture_info.get("venue", {})

                    event_date_str = fixture_info.get("date")
                    event_date = None
                    if event_date_str:
                        try:
                            aware_date = datetime.fromisoformat(event_date_str.replace('Z', '+00:00'))
                            event_date = aware_date.astimezone(timezone.utc)
                        except Exception as e:
                            logger.error(f"Date parsing error for fixture {fixture_info.get('id')}: {e}", exc_info=True)

                    home_team_id = teams_info.get("home", {}).get("id")
                    away_team_id = teams_info.get("away", {}).get("id")

                    if not home_team_id or not away_team_id:
                        logger.warning(f"Skipping fixture {fixture_info.get('id')} due to missing team IDs.")
                        continue

                    # Fetch the TeamLeague association for the home team and current season
                    home_association_query = select(models.TeamLeague).filter(
                        models.TeamLeague.team_id == home_team_id,
                        models.TeamLeague.season_year == season_year
                    )
                    home_association = await db.execute(home_association_query).scalar_one_or_none()

                    if not home_association:
                        logger.warning(f"No TeamLeague association found for home team ID {home_team_id} and season {season_year}.")
                        continue  # Skip this fixture

                    home_team = await db.get(models.Team, home_team_id)

                    # Fetch the TeamLeague association for the away team and current season
                    away_association_query = select(models.TeamLeague).filter(
                        models.TeamLeague.team_id == away_team_id,
                        models.TeamLeague.season_year == season_year
                    )
                    away_association = await db.execute(away_association_query).scalar_one_or_none()

                    if not away_association:
                        logger.warning(f"No TeamLeague association found for away team ID {away_team_id} and season {season_year}.")
                        continue  # Skip this fixture 

                    # fetch the Team using team_id
                    away_team = await db.get(models.Team, away_team_id)

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
                                venue = await db.get(models.Venue, venue_id)

                    fixture_id = fixture_info.get("id")
                    if not fixture_id:
                        logger.warning("No fixture ID found in API data; skipping this fixture.")
                        continue

                    status_short = fixture_info.get("status", {}).get("short")
                    final_statuses = {"FT", "AET", "PEN", "AWD", "WO"}
                    is_final = status_short in final_statuses

                    existing_fixture_query = select(models.Fixture).filter(models.Fixture.fixture_id == fixture_id)
                    existing_fixture_result = await db.execute(existing_fixture_query)
                    existing_fixture = existing_fixture_result.scalars().one_or_none()

                    if not existing_fixture:
                        # Insert new fixture
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
                            is_final=is_final
                        )
                        db.add(fixture)
                        try:
                            await db.commit()
                            await db.refresh(fixture)
                            fixtures_processed += 1
                            logger.info(f"Fixture ID {fixture_id} added to the database.")
                        except IntegrityError:
                            await db.rollback()
                            existing_fixture = await db.get(models.Fixture, fixture_id)
                            if not existing_fixture:
                                continue
                    else:
                        # Update existing fixture if needed
                        fixture_changed = False
                        new_status_short = fixture_info.get("status", {}).get("short")
                        if existing_fixture.status_short != new_status_short:
                            existing_fixture.status_short = new_status_short
                            fixture_changed = True
                            existing_fixture.is_final = new_status_short in final_statuses

                        new_goals_home = goals_info.get("home")
                        new_goals_away = goals_info.get("away")
                        if existing_fixture.goals_home != new_goals_home:
                            existing_fixture.goals_home = new_goals_home
                            fixture_changed = True
                        if existing_fixture.goals_away != new_goals_away:
                            existing_fixture.goals_away = new_goals_away
                            fixture_changed = True

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
                            logger.info(f"Fixture ID {existing_fixture.fixture_id} updated.")

        logger.info(f"Finished fetching and storing fixtures. Total fixtures processed: {fixtures_processed}")
        return {"message": "Fixtures fetched and stored successfully", "processed": fixtures_processed}

    except Exception as e:
        logger.error(f"An error occurred during fixture ingestion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
