# app/crud.py

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from . import models
from typing import Optional

async def get_league(db: AsyncSession, league_id: int) -> Optional[models.League]:
    result = await db.execute(select(models.League).filter(models.League.league_id == league_id))
    return result.scalar_one_or_none()

async def create_league(db: AsyncSession, league: models.League):
    db.add(league)
    await db.commit()
    await db.refresh(league)
    return league

async def get_season(db: AsyncSession, league_id: int, year: int) -> Optional[models.Season]:
    result = await db.execute(
        select(models.Season).filter(
            models.Season.league_id == league_id,
            models.Season.year == year
        )
    )
    return result.scalar_one_or_none()

async def create_season(db: AsyncSession, season: models.Season):
    db.add(season)
    await db.commit()
    await db.refresh(season)
    return season
