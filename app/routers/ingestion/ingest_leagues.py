# app/routers/leagues.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app import models
import logging
import os
import httpx
from datetime import datetime

router = APIRouter(
    prefix="/leagues",
    tags=["leagues"]
)

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")

@router.post("/", response_model=dict)
async def fetch_and_store_leagues(db: AsyncSession = Depends(get_db)):
    try:
        league_ids = [39, 135, 140]  # Premier League, Serie A, La Liga
        url = "https://v3.football.api-sports.io/leagues"
        headers = {
            'x-apisports-key': API_FOOTBALL_KEY
        }
        params = {
            'current': 'true'  # Fetch only current leagues
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, params=params)
            logging.info(f"API Response Status Code: {response.status_code}")
            if response.status_code != 200:
                logging.error(f"API Error: {response.text}")
                raise HTTPException(status_code=500, detail=f"Error fetching data from API: {response.status_code} - {response.text}")
            data = response.json()
            logging.info(f"Fetched {len(data.get('response', []))} current leagues from API.")

        leagues = data.get("response", [])

        for item in leagues:
            league_info = item.get("league", {})
            league_id = league_info.get("id")
            if league_id not in league_ids:
                continue  # Skip leagues not in our list

            country_info = item.get("country", {})
            seasons = item.get("seasons", [])

            # Proceed to store the league
            league = models.League(
                league_id=league_id,
                name=league_info.get("name"),
                type=league_info.get("type"),
                logo=league_info.get("logo"),
                country_name=country_info.get("name"),
                country_code=country_info.get("code"),
                country_flag=country_info.get("flag"),
            )

            # Check if the league already exists in the database
            existing_league = await db.execute(
                select(models.League).filter(models.League.league_id == league.league_id)
            )
            result_league = existing_league.scalar_one_or_none()
            if not result_league:
                db.add(league)
                await db.commit()
                await db.refresh(league)
                logging.info(f"League {league.name} added to the database.")
            else:
                logging.info(f"League {league.name} already exists in the database.")
                league = result_league  # Use the existing league object

            # Store seasons
            for season in seasons:
                # Handle dates carefully
                try:
                    start_date = datetime.strptime(season.get("start"), "%Y-%m-%d").date() if season.get("start") else None
                    end_date = datetime.strptime(season.get("end"), "%Y-%m-%d").date() if season.get("end") else None
                except Exception as date_exception:
                    logging.error(f"Date parsing error: {date_exception}")
                    start_date = None
                    end_date = None

                season_data = models.Season(
                    league_id=league_id,
                    year=season.get("year"),
                    start=start_date,
                    end=end_date,
                    current=season.get("current"),
                    coverage=season.get("coverage")
                )
                # Check if the season already exists in the database
                existing_season = await db.execute(
                    select(models.Season).filter(
                        models.Season.league_id == season_data.league_id,
                        models.Season.year == season_data.year
                    )
                )
                result_season = existing_season.scalar_one_or_none()
                if not result_season:
                    db.add(season_data)
                    await db.commit()
                    await db.refresh(season_data)
                    logging.info(f"Season {season_data.year} for league {league.name} added to the database.")
                else:
                    logging.info(f"Season {season_data.year} for league {league.name} already exists in the database.")
        return {"message": "Leagues and seasons fetched and stored successfully"}
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))
