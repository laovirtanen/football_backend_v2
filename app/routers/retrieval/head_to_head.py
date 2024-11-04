# app/routers/retrieval/head_to_head.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from sqlalchemy.orm import selectinload
from typing import List

from app import models, schemas
from app.database import get_db

router = APIRouter(
    prefix="/head-to-head",
    tags=["head-to-head"]
)

@router.get("/", response_model=List[schemas.FixtureBaseDetailed])
async def get_head_to_head_fixtures(
    team1_id: int = Query(..., description="Team 1 ID"),
    team2_id: int = Query(..., description="Team 2 ID"),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve head-to-head fixtures between two teams.
    """
    try:
        query = (
            select(models.Fixture)
            .where(
                or_(
                    (models.Fixture.home_team_id == team1_id) & (models.Fixture.away_team_id == team2_id),
                    (models.Fixture.home_team_id == team2_id) & (models.Fixture.away_team_id == team1_id)
                ),
                models.Fixture.status_short == 'FT'
            )
            .order_by(models.Fixture.date.desc())
            .limit(limit)
            .options(
                selectinload(models.Fixture.home_team),
                selectinload(models.Fixture.away_team),
                selectinload(models.Fixture.league),
                selectinload(models.Fixture.venue),
                selectinload(models.Fixture.odds),
                selectinload(models.Fixture.prediction)
            )
        )
        result = await db.execute(query)
        fixtures = result.scalars().all()
        return [schemas.FixtureBaseDetailed.model_validate(fixture) for fixture in fixtures]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))