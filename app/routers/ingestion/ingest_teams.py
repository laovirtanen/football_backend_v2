# app/routers/ingestion/ingest_teams.py

import logging
import os
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from app.database import get_db
from app import models

router = APIRouter(
    prefix="/teams",
    tags=["teams"]
)

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.post("/", response_model=dict)
async def fetch_and_store_teams(db: AsyncSession = Depends(get_db)):
    try:
        # Fetch all current seasons with their associated leagues
        seasons_result = await db.execute(
            select(models.Season)
            .options(joinedload(models.Season.league))
            .filter(models.Season.current == True)
        )
        seasons = seasons_result.scalars().all()

        if not seasons:
            logger.info("No current seasons found.")
            return {"message": "No current seasons found."}

        if not API_FOOTBALL_KEY:
            logger.error("API_FOOTBALL_KEY environment variable is not set.")
            raise HTTPException(status_code=500, detail="API key not configured.")

        headers = {
            'x-apisports-key': API_FOOTBALL_KEY,
            'Accept': 'application/json'
        }

        async with httpx.AsyncClient() as client:
            for season in seasons:
                league_id = season.league_id
                season_year = season.year
                league_name = season.league.name


                url = "https://v3.football.api-sports.io/teams"
                params = {
                    'league': league_id,
                    'season': season_year
                }

                logger.info(f"Fetching team data from {url} with params {params}")
                response = await client.get(url, headers=headers, params=params)

                if response.status_code != 200:
                    logger.error(f"API Error for league {league_name} ({league_id}): {response.status_code} - {response.text}")
                    continue

                data = response.json()
                teams = data.get("response", [])
                logger.info(f"Fetched {len(teams)} teams for {league_name} in season {season_year}.")

                total_fetched = len(teams)
                total_skipped = 0  # can be used for additional tracking
                teams_to_add = []
                associations_to_add = []

                for item in teams:
                    team_info = item.get("team", {})

                    # Extract team details
                    team_id = team_info.get("id")
                    team_name = team_info.get("name")

                    if not team_id or not team_name:
                        logger.warning("Team information incomplete; skipping.")
                        total_skipped += 1
                        continue

                    # Check if the team exists; else create it
                    existing_team_result = await db.execute(
                        select(models.Team).filter(models.Team.team_id == team_id)
                    )
                    team = existing_team_result.scalar_one_or_none()

                    if not team:
                        team = models.Team(
                            team_id=team_id,
                            name=team_name,
                            code=team_info.get("code"),
                            country=team_info.get("country"),
                            founded=team_info.get("founded"),
                            national=team_info.get("national"),
                            logo=team_info.get("logo")
                        )
                        teams_to_add.append(team)
                        logger.info(f"New team added: {team_name} (ID: {team_id})")

                    # Create association with the league and season
                    association = models.TeamLeague(
                        team=team,
                        league_id=league_id,
                        season_year=season_year
                    )

                    # Check if the association already exists
                    existing_association_result = await db.execute(
                        select(models.TeamLeague).filter(
                            models.TeamLeague.team_id == team_id,
                            models.TeamLeague.league_id == league_id,
                            models.TeamLeague.season_year == season_year
                        )
                    )
                    existing_assoc = existing_association_result.scalar_one_or_none()

                    if not existing_assoc:
                        associations_to_add.append(association)
                    else:
                        logger.info(f"Association already exists for team {team_name} (ID: {team_id}), league {league_name}, season {season_year}.")

                # add new teams
                if teams_to_add:
                    db.add_all(teams_to_add)
                    await db.commit()
                    for t in teams_to_add:
                        logger.info(f"Team {t.name} (ID: {t.team_id}) added.")

                # add new associations
                if associations_to_add:
                    db.add_all(associations_to_add)
                    await db.commit()
                    for assoc in associations_to_add:
                        logger.info(f"Association added: Team ID {assoc.team_id}, League ID {assoc.league_id}, Season {assoc.season_year}.")

                logger.info(f"Fetched {total_fetched} teams, skipped {total_skipped} teams for {league_name}.")

        return {"message": "Teams fetched and stored successfully"}
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
