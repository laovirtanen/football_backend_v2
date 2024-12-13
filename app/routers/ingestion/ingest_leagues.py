import logging
import os
import httpx
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app import models

router = APIRouter(
    prefix="/leagues",
    tags=["leagues"]
)

# Create a logger for this module
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)  # Ensure DEBUG logging is enabled

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")

@router.post("/", response_model=dict)
async def fetch_and_store_leagues(db: AsyncSession = Depends(get_db)):
    logger.info("Starting leagues ingestion.")
    # Debug: Current league ids selected
    league_ids = [39, 135, 140, 78, 61, 3, 2]  # Premier League, Serie A, La Liga, Bundesliga, Ligue 1, Europa league, Champions league
    logger.debug(f"Target league_ids: {league_ids}")

    # Validate API key
    if not API_FOOTBALL_KEY:
        logger.error("API_FOOTBALL_KEY environment variable is not set.")
        raise HTTPException(status_code=500, detail="API key not configured.")

    headers = {
        'x-apisports-key': API_FOOTBALL_KEY,
        'Accept': 'application/json'
    }

    async with httpx.AsyncClient() as client:
        for league_id in league_ids:
            url = "https://v3.football.api-sports.io/leagues"
            params = {
                'id': league_id
            }

            logger.debug(f"Fetching league data from {url} with params {params}")
            response = await client.get(url, headers=headers, params=params)
            logger.debug(f"API response status for league {league_id}: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"API Error for league {league_id}: {response.status_code} - {response.text}")
                continue  # Move to next league

            try:
                data = response.json()
                logger.debug(f"League {league_id} raw API response: {data}")
            except ValueError as e:
                logger.error(f"JSON decoding error for league {league_id}: {e}")
                continue  # Skip this league

            league_response = data.get("response", [])
            if not league_response:
                logger.warning(f"No data found for league {league_id} in API response.")
                continue  # Move to the next league ID

            # Extract league info
            league_info_data = league_response[0].get("league", {})
            country_info = league_response[0].get("country", {})
            seasons_data = league_response[0].get("seasons", [])

            logger.debug(f"League {league_id} info: {league_info_data}")
            logger.debug(f"League {league_id} country info: {country_info}")
            logger.debug(f"League {league_id} seasons: {seasons_data}")

            # Create league model instance
            league = models.League(
                league_id=league_id,
                name=league_info_data.get("name"),
                type=league_info_data.get("type"),
                logo=league_info_data.get("logo"),
                country_name=country_info.get("name"),
                country_code=country_info.get("code"),
                country_flag=country_info.get("flag"),
            )

            # Check if the league already exists
            existing_league_query = select(models.League).filter(models.League.league_id == league.league_id)
            existing_league_result = await db.execute(existing_league_query)
            existing_league = existing_league_result.scalars().one_or_none()

            if not existing_league:
                logger.debug(f"Inserting new league: {league.name} (ID: {league_id})")
                db.add(league)
                await db.commit()
                await db.refresh(league)
                logger.info(f"League {league.name} (ID: {league_id}) added to the database.")
            else:
                logger.info(f"League {league.name} (ID: {league_id}) already exists in the database.")
                league = existing_league

            # Process seasons
            if not seasons_data:
                logger.warning(f"No seasons found for league {league_id}.")
            else:
                for season in seasons_data:
                    start_date, end_date = None, None
                    try:
                        if season.get("start"):
                            start_date = datetime.strptime(season.get("start"), "%Y-%m-%d").date()
                        if season.get("end"):
                            end_date = datetime.strptime(season.get("end"), "%Y-%m-%d").date()
                    except Exception as date_exception:
                        logger.error(f"Date parsing error for league {league_id} season: {date_exception}")

                    season_year = season.get("year")
                    current_season_flag = season.get("current") or False

                    logger.debug(f"League {league_id} - Found season: Year={season_year}, Current={current_season_flag}, Start={start_date}, End={end_date}")

                    season_data_obj = models.Season(
                        league_id=league_id,
                        year=season_year,
                        start=start_date,
                        end=end_date,
                        current=current_season_flag,
                        coverage=season.get("coverage")
                    )

                    existing_season_query = select(models.Season).filter(
                        models.Season.league_id == league_id,
                        models.Season.year == season_year
                    )
                    existing_season_result = await db.execute(existing_season_query)
                    existing_season = existing_season_result.scalars().one_or_none()

                    if not existing_season:
                        logger.debug(f"Inserting new season for league {league_id}, year {season_year}")
                        db.add(season_data_obj)
                        await db.commit()
                        await db.refresh(season_data_obj)
                        logger.info(f"Season {season_data_obj.year} for league ID {league_id} added to the database.")
                    else:
                        season_fields_updated = False
                        if existing_season.current != current_season_flag:
                            logger.debug(f"Updating current flag for season {season_year} of league {league_id} from {existing_season.current} to {current_season_flag}")
                            existing_season.current = current_season_flag
                            season_fields_updated = True

                        if season_fields_updated:
                            await db.commit()
                            logger.info(f"Season {season_year} for league ID {league_id} updated in the database.")
                        else:
                            logger.debug(f"Season {season_year} for league ID {league_id} is unchanged.")

    # After ingestion, let's log what leagues are in the database
    all_leagues = await db.execute(select(models.League))
    leagues_in_db = all_leagues.scalars().all()
    logger.debug("Leagues currently in DB:")
    for lg in leagues_in_db:
        logger.debug(f" - ID: {lg.league_id}, Name: {lg.name}")

    return {"message": "Leagues and seasons fetched and stored successfully"}
