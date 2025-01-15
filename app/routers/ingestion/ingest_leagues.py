# app/routers/ingest_leagues.py

import logging
import os
import httpx
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.database import get_db
from app import models

router = APIRouter(
    prefix="/leagues",
    tags=["leagues"]
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) 

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
            try:
                response = await client.get(url, headers=headers, params=params)
            except httpx.RequestError as e:
                logger.error(f"Request error for league {league_id}: {e}")
                continue  

            logger.debug(f"API response status for league {league_id}: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"API Error for league {league_id}: {response.status_code} - {response.text}")
                continue  

            try:
                data = response.json()
                logger.debug(f"League {league_id} raw API response: {data}")
            except ValueError as e:
                logger.error(f"JSON decoding error for league {league_id}: {e}")
                continue  #

            league_response = data.get("response", [])
            if not league_response:
                logger.warning(f"No data found for league {league_id} in API response.")
                continue 

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
                try:
                    logger.debug(f"Inserting new league: {league.name} (ID: {league_id})")
                    db.add(league)
                    await db.commit()
                    await db.refresh(league)
                    logger.info(f"League {league.name} (ID: {league_id}) added to the database.")
                except Exception as e:
                    logger.error(f"Error inserting league {league_id}: {e}")
                    await db.rollback()
                    continue  # Skip processing seasons for this league
            else:
                logger.info(f"League {league.name} (ID: {league_id}) already exists in the database.")
                league = existing_league

            # Process seasons: Only current season
            current_seasons = [s for s in seasons_data if s.get("current")]
            if not current_seasons:
                logger.warning(f"No current season found for league {league_id}.")
                continue  

            for season in current_seasons:
                start_date, end_date = None, None
                try:
                    if season.get("start"):
                        start_date = datetime.strptime(season.get("start"), "%Y-%m-%d").date()
                    if season.get("end"):
                        end_date = datetime.strptime(season.get("end"), "%Y-%m-%d").date()
                except Exception as date_exception:
                    logger.error(f"Date parsing error for league {league_id} season: {date_exception}")
                    continue  

                season_year = season.get("year")
                current_season_flag = season.get("current") or False

                logger.debug(f"League {league_id} - Found current season: Year={season_year}, Current={current_season_flag}, Start={start_date}, End={end_date}")

                # Ensure only one current season per league
                # Mark existing current seasons as False
                try:
                    update_stmt = update(models.Season).where(
                        models.Season.league_id == league_id,
                        models.Season.current == True
                    ).values(current=False)
                    await db.execute(update_stmt)
                    logger.debug(f"Marked all existing seasons for league {league_id} as non-current.")
                except Exception as e:
                    logger.error(f"Error updating existing seasons for league {league_id}: {e}")
                    await db.rollback()
                    continue  # Skip updating current season

                # Create or update the current season
                season_data_obj = models.Season(
                    league_id=league_id,
                    year=season_year,
                    start_date=start_date,    
                    end_date=end_date,        
                    current=current_season_flag,
                    coverage=season.get("coverage")
                )

                # Check if the current season already exists
                existing_season_query = select(models.Season).filter(
                    models.Season.league_id == league_id,
                    models.Season.year == season_year
                )
                existing_season_result = await db.execute(existing_season_query)
                existing_season = existing_season_result.scalars().one_or_none()

                if not existing_season:
                    try:
                        logger.debug(f"Inserting new current season for league {league_id}, year {season_year}")
                        db.add(season_data_obj)
                        await db.commit()
                        await db.refresh(season_data_obj)
                        logger.info(f"Season {season_data_obj.year} for league ID {league_id} added to the database.")
                    except Exception as e:
                        logger.error(f"Error inserting season {season_year} for league {league_id}: {e}")
                        await db.rollback()
                        continue  
                else:
                    try:
                        logger.debug(f"Updating existing current season for league {league_id}, year {season_year}")
                        existing_season.current = current_season_flag
                        existing_season.start_date = start_date    
                        existing_season.end_date = end_date        
                        existing_season.coverage = season.get("coverage")
                        await db.commit()
                        logger.info(f"Season {existing_season.year} for league ID {league_id} updated in the database.")
                    except Exception as e:
                        logger.error(f"Error updating season {season_year} for league {league_id}: {e}")
                        await db.rollback()
                        continue  

    # log what leagues are in the database
    all_leagues = await db.execute(select(models.League))
    leagues_in_db = all_leagues.scalars().all()
    logger.debug("Leagues currently in DB:")
    for lg in leagues_in_db:
        logger.debug(f" - ID: {lg.league_id}, Name: {lg.name}")

    return {"message": "Leagues and current seasons fetched and stored successfully"}
