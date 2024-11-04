# app/routers/retrieval/players.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app import models, schemas
from app.database import get_db

router = APIRouter(
    prefix="/players",
    tags=["players"]
)

@router.get("/", response_model=List[schemas.PlayerBase])
async def get_players(
    db: AsyncSession = Depends(get_db),
    team_id: Optional[int] = Query(None, description="Filter by team ID"),
    league_id: Optional[int] = Query(None, description="Filter by league ID"),
    season_year: Optional[int] = Query(None, description="Filter by season year"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Retrieve a list of players with optional filters.
    """
    try:
        query = select(models.Player)
        
        if team_id:
            query = query.where(models.Player.team_id == team_id)
        if league_id:
            query = query.join(models.Player.team).where(models.Team.league_id == league_id)
        if season_year:
            query = query.where(models.Player.season_year == season_year)
        
        query = query.options(
            selectinload(models.Player.team),
            selectinload(models.Player.statistics)
        ).offset(offset).limit(limit)
        
        result = await db.execute(query)
        players = result.scalars().all()
        return [schemas.PlayerBase.model_validate(player) for player in players]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{player_id}", response_model=schemas.PlayerBase)
async def get_player_by_id(
    player_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a specific player by their ID.
    """
    try:
        query = select(models.Player).where(models.Player.player_id == player_id).options(
            selectinload(models.Player.team),
            selectinload(models.Player.statistics)
        )
        result = await db.execute(query)
        player = result.scalar_one_or_none()
        if not player:
            raise HTTPException(status_code=404, detail="Player not found")
        return schemas.PlayerBase.model_validate(player)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# app/routers/retrieval/players.py

@router.get("/stats/rankings", response_model=List[schemas.PlayerRanking])
async def get_player_rankings(
    stat_type: str = Query(..., description="Statistic type to rank players by", regex="^(goals|assists|yellow_cards|red_cards)$"),
    league_id: Optional[int] = Query(None, description="Filter by league ID"),
    season_year: Optional[int] = Query(None, description="Filter by season year"),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve player rankings based on a specific statistic.
    """
    try:
        # Map stat_type to database column
        stat_column_mapping = {
            'goals': models.PlayerStatistics.goals_total,
            'assists': models.PlayerStatistics.goals_assists,
            'yellow_cards': models.PlayerStatistics.cards_yellow,
            'red_cards': models.PlayerStatistics.cards_red
        }

        stat_column = stat_column_mapping.get(stat_type)

        if not stat_column:
            raise HTTPException(status_code=400, detail="Invalid stat_type")

        stat_value = func.sum(stat_column).label('stat_value')

        query = (
            select(
                models.Player,
                stat_value
            )
            .join(models.PlayerStatistics, models.Player.player_id == models.PlayerStatistics.player_id)
            .group_by(models.Player.player_id)
            .order_by(stat_value.desc())
            .limit(limit)
        )

        if league_id:
            query = query.where(models.PlayerStatistics.league_id == league_id)
        if season_year:
            query = query.where(models.PlayerStatistics.season_year == season_year)

        result = await db.execute(query)
        rankings = result.fetchall()

        rankings_list = []
        rank = 1
        for row in rankings:
            player = row[0]
            stat_value_result = row[1]
            rankings_list.append(schemas.PlayerRanking(
                rank=rank,
                player=schemas.PlayerBase.model_validate(player),
                stat_value=stat_value_result or 0
            ))
            rank += 1

        return rankings_list

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
