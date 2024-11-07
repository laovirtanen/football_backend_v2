# app/routers/retrieval/fixtures.py

from fastapi import APIRouter, Depends, HTTPException, Path, Query
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


@router.get("/", response_model=List[schemas.FixtureBaseDetailed])
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
    try:
        # Build the initial query for fixture IDs
        fixture_ids_query = select(models.Fixture.fixture_id)

        if league_id:
            fixture_ids_query = fixture_ids_query.where(models.Fixture.league_id == league_id)
        if team_id:
            fixture_ids_query = fixture_ids_query.where(
                (models.Fixture.home_team_id == team_id) | 
                (models.Fixture.away_team_id == team_id)
            )
        if date_from:
            fixture_ids_query = fixture_ids_query.where(models.Fixture.date >= date_from)
        if date_to:
            fixture_ids_query = fixture_ids_query.where(models.Fixture.date <= date_to)
        if status:
            fixture_ids_query = fixture_ids_query.where(models.Fixture.status_short.ilike(f"%{status}%"))

        fixture_ids_query = fixture_ids_query.offset(offset).limit(limit)

        # Execute the query to get fixture IDs
        result = await db.execute(fixture_ids_query)
        fixture_ids = result.scalars().all()

        if not fixture_ids:
            return []

        # Now fetch the fixtures with relationships
        fixtures_query = (
            select(models.Fixture)
            .where(models.Fixture.fixture_id.in_(fixture_ids))
            .options(
                selectinload(models.Fixture.home_team),
                selectinload(models.Fixture.away_team),
                selectinload(models.Fixture.league),
                selectinload(models.Fixture.venue),
                selectinload(models.Fixture.prediction),
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
            )
        )

        fixtures_result = await db.execute(fixtures_query)
        fixtures = fixtures_result.scalars().all()
        return fixtures
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
    



@router.get("/{fixture_id}", response_model=schemas.FixtureBaseDetailed)
async def get_fixture_by_id(
    fixture_id: int = Path(..., description="The ID of the fixture to retrieve"),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a specific fixture by its ID.
    """
    try:
        query = select(models.Fixture).where(models.Fixture.fixture_id == fixture_id).options(
            selectinload(models.Fixture.home_team),
            selectinload(models.Fixture.away_team),
            selectinload(models.Fixture.league),
            selectinload(models.Fixture.venue),
            selectinload(models.Fixture.prediction),
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
        )
        result = await db.execute(query)
        fixture = result.scalars().first()
        if not fixture:
            raise HTTPException(status_code=404, detail="Fixture not found")
        return fixture
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))