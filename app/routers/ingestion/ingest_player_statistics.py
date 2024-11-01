# app/routers/ingestion/ingest_player_statistics.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app import models
import logging
import os
import httpx
import asyncio

router = APIRouter(
    prefix="/player_statistics",
    tags=["player_statistics"]
)

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")

@router.post("/", response_model=dict)
async def fetch_and_store_player_statistics(db: AsyncSession = Depends(get_db)):
    try:
        # Fetch current seasons
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

            # Fetch teams for this season and league
            teams_result = await db.execute(
                select(models.Team).filter(
                    models.Team.league_id == league_id,
                    models.Team.season_year == season_year
                )
            )
            teams = teams_result.scalars().all()

            for team in teams:
                team_id = team.team_id

                page = 1
                total_pages = 1

                while page <= total_pages:
                    # Fetch players and their statistics per team
                    url = f"https://v3.football.api-sports.io/players"
                    params = {
                        'team': team_id,
                        'season': season_year,
                        'league': league_id,
                        'page': page
                    }

                    async with httpx.AsyncClient() as client:
                        response = await client.get(url, headers=headers, params=params)
                        if response.status_code != 200:
                            logging.error(f"API Error: {response.text}")
                            break  # Skip to next team

                        data = response.json()
                        logging.info(f"Fetched page {page} for team {team.name} in season {season_year}.")

                    stats_response = data.get("response", [])
                    if not stats_response:
                        logging.warning(f"No statistics found for team {team.name} on page {page}.")
                        break  # No data, move to next team

                    for player_data in stats_response:
                        player_info = player_data.get("player", {})
                        statistics_list = player_data.get("statistics", [])

                        if not player_info or not statistics_list:
                            continue

                        player_id = player_info.get("id")

                        # Ensure player exists in the database
                        existing_player = await db.execute(
                            select(models.Player).filter(
                                models.Player.player_id == player_id,
                                models.Player.team_id == team_id,
                                models.Player.season_year == season_year
                            )
                        )
                        player = existing_player.scalar_one_or_none()

                        if not player:
                            # If the player is not in the database, skip (or optionally add them)
                            logging.warning(f"Player {player_info.get('name')} not found in database.")
                            continue

                        for stats_data in statistics_list:
                            # Ensure league and season match
                            if stats_data.get("league", {}).get("id") != league_id or stats_data.get("league", {}).get("season") != season_year:
                                continue

                            # Extract statistics data
                            game_stats = stats_data.get("games", {})
                            subs_stats = stats_data.get("substitutes", {})
                            shots_stats = stats_data.get("shots", {})
                            goals_stats = stats_data.get("goals", {})
                            passes_stats = stats_data.get("passes", {})
                            tackles_stats = stats_data.get("tackles", {})
                            duels_stats = stats_data.get("duels", {})
                            dribbles_stats = stats_data.get("dribbles", {})
                            fouls_stats = stats_data.get("fouls", {})
                            cards_stats = stats_data.get("cards", {})
                            penalty_stats = stats_data.get("penalty", {})

                            # Create or update PlayerStatistics instance
                            existing_stat = await db.execute(
                                select(models.PlayerStatistics).filter(
                                    models.PlayerStatistics.player_id == player_id,
                                    models.PlayerStatistics.team_id == team_id,
                                    models.PlayerStatistics.league_id == league_id,
                                    models.PlayerStatistics.season_year == season_year
                                )
                            )
                            result_stat = existing_stat.scalar_one_or_none()

                            if not result_stat:
                                player_stat = models.PlayerStatistics(
                                    player_id=player_id,
                                    team_id=team_id,
                                    league_id=league_id,
                                    season_year=season_year,
                                    appearances=game_stats.get("appearences"),
                                    lineups=game_stats.get("lineups"),
                                    minutes=game_stats.get("minutes"),
                                    number=game_stats.get("number"),
                                    position=game_stats.get("position"),
                                    rating=float(game_stats.get("rating")) if game_stats.get("rating") else None,
                                    captain=game_stats.get("captain"),

                                    subs_in=subs_stats.get("in"),
                                    subs_out=subs_stats.get("out"),
                                    subs_bench=subs_stats.get("bench"),

                                    shots_total=shots_stats.get("total"),
                                    shots_on=shots_stats.get("on"),

                                    goals_total=goals_stats.get("total"),
                                    goals_conceded=goals_stats.get("conceded"),
                                    goals_assists=goals_stats.get("assists"),
                                    goals_saves=goals_stats.get("saves"),

                                    passes_total=passes_stats.get("total"),
                                    passes_key=passes_stats.get("key"),
                                    passes_accuracy=int(passes_stats.get("accuracy")) if passes_stats.get("accuracy") else None,

                                    tackles_total=tackles_stats.get("total"),
                                    tackles_blocks=tackles_stats.get("blocks"),
                                    tackles_interceptions=tackles_stats.get("interceptions"),

                                    duels_total=duels_stats.get("total"),
                                    duels_won=duels_stats.get("won"),

                                    dribbles_attempts=dribbles_stats.get("attempts"),
                                    dribbles_success=dribbles_stats.get("success"),
                                    dribbles_past=dribbles_stats.get("past"),

                                    fouls_drawn=fouls_stats.get("drawn"),
                                    fouls_committed=fouls_stats.get("committed"),

                                    cards_yellow=cards_stats.get("yellow"),
                                    cards_yellowred=cards_stats.get("yellowred"),
                                    cards_red=cards_stats.get("red"),

                                    penalty_won=penalty_stats.get("won"),
                                    penalty_committed=penalty_stats.get("commited"),
                                    penalty_scored=penalty_stats.get("scored"),
                                    penalty_missed=penalty_stats.get("missed"),
                                    penalty_saved=penalty_stats.get("saved")
                                )
                                db.add(player_stat)
                                await db.commit()
                                await db.refresh(player_stat)
                                logging.info(f"Statistics for player {player.name} added to the database.")
                            else:
                                # Update existing statistics
                                fields_to_update = {
                                    'appearances': game_stats.get("appearences"),
                                    'lineups': game_stats.get("lineups"),
                                    'minutes': game_stats.get("minutes"),
                                    'number': game_stats.get("number"),
                                    'position': game_stats.get("position"),
                                    'rating': float(game_stats.get("rating")) if game_stats.get("rating") else None,
                                    'captain': game_stats.get("captain"),
                                    'subs_in': subs_stats.get("in"),
                                    'subs_out': subs_stats.get("out"),
                                    'subs_bench': subs_stats.get("bench"),
                                    'shots_total': shots_stats.get("total"),
                                    'shots_on': shots_stats.get("on"),
                                    'goals_total': goals_stats.get("total"),
                                    'goals_conceded': goals_stats.get("conceded"),
                                    'goals_assists': goals_stats.get("assists"),
                                    'goals_saves': goals_stats.get("saves"),
                                    'passes_total': passes_stats.get("total"),
                                    'passes_key': passes_stats.get("key"),
                                    'passes_accuracy': int(passes_stats.get("accuracy")) if passes_stats.get("accuracy") else None,
                                    'tackles_total': tackles_stats.get("total"),
                                    'tackles_blocks': tackles_stats.get("blocks"),
                                    'tackles_interceptions': tackles_stats.get("interceptions"),
                                    'duels_total': duels_stats.get("total"),
                                    'duels_won': duels_stats.get("won"),
                                    'dribbles_attempts': dribbles_stats.get("attempts"),
                                    'dribbles_success': dribbles_stats.get("success"),
                                    'dribbles_past': dribbles_stats.get("past"),
                                    'fouls_drawn': fouls_stats.get("drawn"),
                                    'fouls_committed': fouls_stats.get("committed"),
                                    'cards_yellow': cards_stats.get("yellow"),
                                    'cards_yellowred': cards_stats.get("yellowred"),
                                    'cards_red': cards_stats.get("red"),
                                    'penalty_won': penalty_stats.get("won"),
                                    'penalty_committed': penalty_stats.get("commited"),
                                    'penalty_scored': penalty_stats.get("scored"),
                                    'penalty_missed': penalty_stats.get("missed"),
                                    'penalty_saved': penalty_stats.get("saved")
                                }

                                for field, value in fields_to_update.items():
                                    setattr(result_stat, field, value)
                                await db.commit()
                                logging.info(f"Statistics for player {player.name} updated in the database.")

                    # Handle pagination
                    paging = data.get("paging", {})
                    total_pages = paging.get("total", 1)
                    current_page = paging.get("current", 1)
                    if current_page >= total_pages:
                        break
                    else:
                        page += 1

                    # Optional delay to respect rate limits
                    await asyncio.sleep(0.5)

        return {"message": "Player statistics fetched and stored successfully"}

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise HTTPException(status_code=500, detail=str(e))
