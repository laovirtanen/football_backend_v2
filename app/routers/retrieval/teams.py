# app/routers/retrieval/teams.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional

from app import models, schemas
from app.database import get_db

router = APIRouter(
    prefix="/teams",
    tags=["teams"]
)

@router.get("/", response_model=List[schemas.TeamBase])
async def get_teams(
    db: AsyncSession = Depends(get_db),
    league_id: Optional[int] = Query(None, description="Filter by league ID"),
    season_year: Optional[int] = Query(None, description="Filter by season year"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Retrieve a list of teams with optional filters.
    """
    try:
        query = select(models.Team)
        if league_id:
            query = query.where(models.Team.league_id == league_id)
        if season_year:
            query = query.where(models.Team.season_year == season_year)
        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        teams = result.scalars().all()
        return teams
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{team_id}", response_model=schemas.TeamBase)
async def get_team_by_id(
    team_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a specific team by its ID.
    """
    try:
        result = await db.execute(select(models.Team).where(models.Team.team_id == team_id))
        team = result.scalar_one_or_none()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        return team
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
