# app/routers/retrieval/leagues.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from sqlalchemy.orm import selectinload


from app import models, schemas
from app.database import get_db

router = APIRouter(
    prefix="/leagues",
    tags=["leagues"]
)

@router.get("/", response_model=List[schemas.LeagueBase])
async def get_leagues(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Retrieve a list of leagues.
    """
    try:
        result = await db.execute(select(models.League).offset(offset).limit(limit))
        leagues = result.scalars().all()
        return leagues
    except Exception as e:
        import logging
        logging.error(f"Error fetching leagues: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/{league_id}", response_model=schemas.LeagueWithTeams)
async def get_league_by_id(
    league_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a specific league by its ID, including its teams.
    """
    try:
        result = await db.execute(
            select(models.League)
            .where(models.League.league_id == league_id)
            .options(
                selectinload(models.League.teams).selectinload(models.TeamLeague.team)
            )
        )
        league = result.scalar_one_or_none()
        if not league:
            raise HTTPException(status_code=404, detail="League not found")
        return league
    except Exception as e:
        import logging
        logging.error(f"Error fetching league by ID {league_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")