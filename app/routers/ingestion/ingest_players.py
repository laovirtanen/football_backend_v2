# app/routers/ingestion/ingest_players.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app import models
import logging
import os
import httpx
import asyncio
from datetime import datetime

router = APIRouter(
    prefix="/players",
    tags=["players"]
)

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")

@router.post("/", response_model=dict)
async def fetch_and_store_players(db: AsyncSession = Depends(get_db)):
    try:
        # Fetch teams for the current season
        seasons_result = await db.execute(
            select(models.Season).filter(models.Season.current == True)
        )
        seasons = seasons_result.scalars().all()

        if not seasons:
            logging.info("No current seasons found.")
            return {"message": "No current seasons found."}

        headers = {
            'x-apisports-key': API_FOOTBALL_KEY
        }

        for season in seasons:
            season_year = season.year
            league_id = season.league_id

            # Fetch teams for this season
            teams_result = await db.execute(
                select(models.Team).filter(
                    models.Team.league_id == league_id,
                    models.Team.season_year == season_year
                )
            )
            teams = teams_result.scalars().all()

            for team in teams:
                team_id = team.team_id

                # Fetch players for the team and season
                url = f"https://v3.football.api-sports.io/players?team={team_id}&season={season_year}"
                page = 1
                total_pages = 1

                while page <= total_pages:
                    params = {
                        'team': team_id,
                        'season': season_year,
                        'page': page
                    }

                    async with httpx.AsyncClient() as client:
                        response = await client.get(url, headers=headers, params=params)
                        if response.status_code != 200:
                            logging.error(f"API Error: {response.text}")
                            break  # Move to next team

                        data = response.json()
                        logging.info(f"Fetched {len(data.get('response', []))} players for team {team.name} on page {page}.")

                    players_data = data.get("response", [])

                    for item in players_data:
                        player_info = item.get("player", {})

                        # Parse birth date
                        birth_date_str = player_info.get("birth", {}).get("date")
                        birth_date = None
                        if birth_date_str:
                            try:
                                birth_date = datetime.strptime(birth_date_str, "%Y-%m-%d").date()
                            except Exception as e:
                                logging.error(f"Error parsing birth date for player {player_info.get('name')}: {e}")

                        player = models.Player(
                            player_id=player_info.get("id"),
                            name=player_info.get("name"),
                            firstname=player_info.get("firstname"),
                            lastname=player_info.get("lastname"),
                            age=player_info.get("age"),
                            birth_date=birth_date,
                            birth_place=player_info.get("birth", {}).get("place"),
                            birth_country=player_info.get("birth", {}).get("country"),
                            nationality=player_info.get("nationality"),
                            height=player_info.get("height"),
                            weight=player_info.get("weight"),
                            injured=player_info.get("injured"),
                            photo=player_info.get("photo"),
                            team_id=team_id,
                            season_year=season_year  # Store the season year
                        )

                        # Check if the player already exists for this season
                        existing_player = await db.execute(
                            select(models.Player).filter(
                                models.Player.player_id == player.player_id,
                                models.Player.season_year == season_year
                            )
                        )
                        result_player = existing_player.scalar_one_or_none()
                        if not result_player:
                            db.add(player)
                            await db.commit()
                            await db.refresh(player)
                            logging.info(f"Player {player.name} added to the database for season {season_year}.")
                        else:
                            logging.info(f"Player {player.name} already exists in the database for season {season_year}.")

                    # Handle pagination
                    paging = data.get("paging", {})
                    total_pages = paging.get("total", 1)
                    current_page = paging.get("current", 1)
                    if page >= total_pages:
                        break
                    else:
                        page += 1

                    # Optional delay to respect rate limits
                    await asyncio.sleep(0.5)

        return {"message": "Players fetched and stored successfully"}
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))
