# app/routers/ingestion/player_statistics.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from app.database import get_db
from app import models
import logging
import os
import httpx
import asyncio
from sqlalchemy.exc import IntegrityError

router = APIRouter(
    prefix="/player_statistics",
    tags=["player_statistics"]
)

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")

@router.post("/", response_model=dict)
async def fetch_and_store_player_statistics(db: AsyncSession = Depends(get_db)):
    try:
        seasons_result = await db.execute(
            select(models.Season).filter(models.Season.current == True)
        )
        seasons = seasons_result.scalars().all()

        if not seasons:
            logging.info("No current seasons found.")
            return {"message": "No current seasons found."}

        if not API_FOOTBALL_KEY:
            logging.error("API_FOOTBALL_KEY environment variable is not set.")
            raise HTTPException(status_code=500, detail="API key not configured.")

        headers = {
            'x-apisports-key': API_FOOTBALL_KEY,
            'Accept': 'application/json'
        }

        async with httpx.AsyncClient() as client:
            for season in seasons:
                season_year = season.year
                league_id = season.league_id

                # Fetch teams via TeamLeague association
                teams_league_result = await db.execute(
                    select(models.TeamLeague).filter(
                        models.TeamLeague.league_id == league_id,
                        models.TeamLeague.season_year == season_year
                    ).options(joinedload(models.TeamLeague.team))
                )
                teams_league = teams_league_result.scalars().all()

                teams = [tl.team for tl in teams_league]

                if not teams:
                    logging.warning(f"No teams found for league ID {league_id} and season {season_year}.")
                    continue  # Skip to the next league

                for team in teams:
                    team_id = team.team_id
                    page = 1
                    total_pages = 1

                    while page <= total_pages:
                        url = "https://v3.football.api-sports.io/players"
                        params = {
                            'team': team_id,
                            'season': season_year,
                            'league': league_id,
                            'page': page
                        }

                        response = await client.get(url, headers=headers, params=params)
                        if response.status_code != 200:
                            logging.error(f"API Error for team {team.name} (ID: {team_id}): {response.status_code} - {response.text}")
                            break

                        try:
                            data = response.json()
                        except ValueError as e:
                            logging.error(f"JSON decoding error for team {team.name} (ID: {team_id}): {e}")
                            break

                        stats_response = data.get("response", [])

                        for player_data in stats_response:
                            player_info = player_data.get("player", {})
                            statistics_list = player_data.get("statistics", [])
                            player_id = player_info.get("id")

                            if not player_id:
                                logging.warning(f"Missing player ID for player data: {player_info}")
                                continue

                            # Fetch Player
                            player = await db.get(models.Player, player_id)
                            if not player:
                                logging.warning(f"Player {player_info.get('name')} (ID: {player_id}) not found in DB.")
                                continue

                            for stats_data in statistics_list:
                                if (stats_data.get("league", {}).get("id") != league_id or
                                        stats_data.get("league", {}).get("season") != season_year):
                                    continue

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

                                # Check if PlayerStatistics already exists
                                existing_stat_result = await db.execute(
                                    select(models.PlayerStatistics).filter(
                                        models.PlayerStatistics.player_id == player_id,
                                        models.PlayerStatistics.team_id == team_id,
                                        models.PlayerStatistics.league_id == league_id,
                                        models.PlayerStatistics.season_year == season_year
                                    )
                                )
                                existing_stat = existing_stat_result.scalar_one_or_none()

                                if not existing_stat:
                                    # Create new PlayerStatistics
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
                                    try:
                                        await db.commit()
                                        await db.refresh(player_stat)
                                        logging.info(f"Statistics for player {player.name} (ID: {player_id}) added.")
                                    except IntegrityError as ie:
                                        await db.rollback()
                                        logging.error(f"IntegrityError while adding statistics for player {player.name} (ID: {player_id}): {ie}")
                                else:
                                    # Update existing PlayerStatistics
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
                                        setattr(existing_stat, field, value)
                                    
                                    try:
                                        await db.commit()
                                        logging.info(f"Statistics for player {player.name} (ID: {player_id}) updated.")
                                    except IntegrityError as ie:
                                        await db.rollback()
                                        logging.error(f"IntegrityError while updating statistics for player {player.name} (ID: {player_id}): {ie}")

                        # Handle pagination
                        paging = data.get("paging", {})
                        total_pages = paging.get("total", 1)
                        current_page = paging.get("current", 1)
                        if current_page >= total_pages:
                            break
                        else:
                            page += 1
                            await asyncio.sleep(0.5)

        return {"message": "Player statistics fetched and stored successfully"}

    except Exception as e:
        logging.error(f"An error occurred: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
