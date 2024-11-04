# app/routers/retrieval/odds.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app import models, schemas
from app.database import get_db

router = APIRouter(
    prefix="/odds",
    tags=["odds"]
)

@router.get("/", response_model=List[schemas.FixtureOddsSchema])
async def get_odds(
    db: AsyncSession = Depends(get_db),
    fixture_id: Optional[int] = Query(None, description="Filter by fixture ID"),
    bookmaker_id: Optional[int] = Query(None, description="Filter by bookmaker ID"),
    bet_type_id: Optional[int] = Query(None, description="Filter by bet type ID"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Retrieve a list of odds with optional filters.
    """
    try:
        query = select(models.FixtureOdds)
        
        if fixture_id:
            query = query.where(models.FixtureOdds.fixture_id == fixture_id)
        if bookmaker_id:
            query = query.join(models.FixtureOdds.fixture_bookmakers).where(models.FixtureBookmaker.bookmaker_id == bookmaker_id)
        if bet_type_id:
            query = query.join(models.FixtureOdds.fixture_bookmakers).join(models.FixtureBookmaker.bets).where(models.Bet.bet_type_id == bet_type_id)
        
        query = query.options(
            selectinload(models.FixtureOdds.fixture_bookmakers).selectinload(models.FixtureBookmaker.bookmaker),
            selectinload(models.FixtureOdds.fixture_bookmakers).selectinload(models.FixtureBookmaker.bets).selectinload(models.Bet.bet_type),
            selectinload(models.FixtureOdds.fixture_bookmakers).selectinload(models.FixtureBookmaker.bets).selectinload(models.Bet.odd_values)
        ).offset(offset).limit(limit)
        
        result = await db.execute(query)
        odds = result.scalars().all()
        return odds
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{odds_id}", response_model=schemas.FixtureOddsSchema)
async def get_odds_by_id(
    odds_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a specific odds entry by its ID, including related bookmakers and bets.
    """
    try:
        query = select(models.FixtureOdds).where(models.FixtureOdds.id == odds_id).options(
            selectinload(models.FixtureOdds.fixture_bookmakers).selectinload(models.FixtureBookmaker.bookmaker),
            selectinload(models.FixtureOdds.fixture_bookmakers).selectinload(models.FixtureBookmaker.bets).selectinload(models.Bet.bet_type),
            selectinload(models.FixtureOdds.fixture_bookmakers).selectinload(models.FixtureBookmaker.bets).selectinload(models.Bet.odd_values)
        )
        result = await db.execute(query)
        odds = result.scalar_one_or_none()
        if not odds:
            raise HTTPException(status_code=404, detail="Odds not found")
        return odds
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
