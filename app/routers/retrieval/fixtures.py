# app/routers/retrieval/fixtures.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload, joinedload
from typing import List, Optional
from datetime import datetime

from app import models, schemas
from app.database import get_db

router = APIRouter(
    prefix="/fixtures",
    tags=["fixtures"]
)

@router.get("/", response_model=List[schemas.FixtureBase])
async def get_fixtures(
    db: AsyncSession = Depends(get_db),
    league_id: Optional[int] = Query(None, description="Filter by league ID"),
    team_id: Optional[int] = Query(None, description="Filter by team ID (home or away)"),
    date_from: Optional[datetime] = Query(None, description="Start date in YYYY-MM-DD format"),
    date_to: Optional[datetime] = Query(None, description="End date in YYYY-MM-DD format"),
    status: Optional[str] = Query(None, description="Filter by match status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Retrieve a list of fixtures with optional filters.
    """
    try:
        query = select(models.Fixture)
        
        if league_id:
            query = query.where(models.Fixture.league_id == league_id)
        if team_id:
            query = query.where(
                (models.Fixture.home_team_id == team_id) | 
                (models.Fixture.away_team_id == team_id)
            )
        if date_from:
            query = query.where(models.Fixture.date >= date_from)
        if date_to:
            query = query.where(models.Fixture.date <= date_to)
        if status:
            query = query.where(models.Fixture.status_short.ilike(f"%{status}%"))
        
        query = query.options(
            selectinload(models.Fixture.home_team),
            selectinload(models.Fixture.away_team),
            selectinload(models.Fixture.league),
            selectinload(models.Fixture.venue),
            selectinload(models.Fixture.odds)
                .selectinload(models.FixtureOdds.fixture_bookmakers)
                .selectinload(models.FixtureBookmaker.bookmaker),
            selectinload(models.Fixture.odds)
                .selectinload(models.FixtureOdds.fixture_bookmakers)
                .selectinload(models.FixtureBookmaker.bets)
                .selectinload(models.Bet.bet_type),
            selectinload(models.Fixture.odds)
                .selectinload(models.FixtureOdds.fixture_bookmakers)
                .selectinload(models.FixtureBookmaker.bets)
                .selectinload(models.Bet.odd_values),
            selectinload(models.Fixture.prediction)
        ).offset(offset).limit(limit)
        
        result = await db.execute(query)
        fixtures = result.scalars().all()
        return fixtures
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))