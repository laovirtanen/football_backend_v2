# app/routers/ingestion/ingest_teams.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from app.database import get_db
from app import models
import logging
import os
import httpx

router = APIRouter(
    prefix="/teams",
    tags=["teams"]
)

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")


@router.post("/", response_model=dict)
async def fetch_and_store_teams(db: AsyncSession = Depends(get_db)):
    try:
        # Fetch current seasons from the database, including the league relationship
        seasons_result = await db.execute(
            select(models.Season).options(selectinload(models.Season.league)).filter(models.Season.current == True)
        )
        seasons = seasons_result.scalars().all()

        if not seasons:
            logging.info("No current seasons found.")
            return {"message": "No current seasons found."}

        headers = {
            'x-apisports-key': API_FOOTBALL_KEY
        }

        for season in seasons:
            league_id = season.league_id
            season_year = season.year  # Use the season's year dynamically
            league_name = season.league.name

            # Fetch teams for the league and season
            url = f"https://v3.football.api-sports.io/teams?league={league_id}&season={season_year}"

            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers)
                if response.status_code != 200:
                    logging.error(f"API Error: {response.text}")
                    continue  # Skip to next season

                data = response.json()
                logging.info(f"Fetched {len(data.get('response', []))} teams for league {league_name} in season {season_year}.")

            teams = data.get("response", [])

            for item in teams:
                team_info = item.get("team", {})

                team = models.Team(
                    team_id=team_info.get("id"),
                    name=team_info.get("name"),
                    code=team_info.get("code"),
                    country=team_info.get("country"),
                    founded=team_info.get("founded"),
                    national=team_info.get("national"),
                    logo=team_info.get("logo"),
                    league_id=league_id,
                    season_year=season_year  # Store the season year
                )

                # Check if the team already exists for this season
                existing_team = await db.execute(
                    select(models.Team).filter(
                        models.Team.team_id == team.team_id,
                        models.Team.season_year == season_year
                    )
                )
                result_team = existing_team.scalar_one_or_none()
                if not result_team:
                    db.add(team)
                    await db.commit()
                    await db.refresh(team)
                    logging.info(f"Team {team.name} added to the database for season {season_year}.")
                else:
                    logging.info(f"Team {team.name} already exists in the database for season {season_year}.")

        return {"message": "Teams fetched and stored successfully"}
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))
