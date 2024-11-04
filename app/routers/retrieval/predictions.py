# app/routers/retrieval/predictions.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func, case
from sqlalchemy.orm import selectinload
from typing import List, Optional

from app import models, schemas
from app.database import get_db

router = APIRouter(
    prefix="/predictions",
    tags=["predictions"]
)

@router.get("/", response_model=List[schemas.PredictionSchema])
async def get_predictions(
    db: AsyncSession = Depends(get_db),
    fixture_id: Optional[int] = Query(None, description="Filter by fixture ID"),
    winner_team_id: Optional[int] = Query(None, description="Filter by winner team ID"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Retrieve a list of predictions with optional filters.
    """
    try:
        query = select(models.Prediction)
        
        if fixture_id:
            query = query.where(models.Prediction.fixture_id == fixture_id)
        if winner_team_id:
            query = query.where(models.Prediction.winner_team_id == winner_team_id)
        
        query = query.options(
            selectinload(models.Prediction.winner_team),
            selectinload(models.Prediction.fixture)
        ).offset(offset).limit(limit)
        
        result = await db.execute(query)
        predictions = result.scalars().all()
        return [schemas.PredictionSchema.model_validate(prediction) for prediction in predictions]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{prediction_id}", response_model=schemas.PredictionSchema)
async def get_prediction_by_id(
    prediction_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a specific prediction by its ID.
    """
    try:
        query = select(models.Prediction).where(models.Prediction.id == prediction_id).options(
            selectinload(models.Prediction.winner_team),
            selectinload(models.Prediction.fixture)
        )
        result = await db.execute(query)
        prediction = result.scalar_one_or_none()
        if not prediction:
            raise HTTPException(status_code=404, detail="Prediction not found")
        return schemas.PredictionSchema.model_validate(prediction)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats/accuracy", response_model=schemas.PredictionAccuracy)
async def get_prediction_accuracy(
    league_id: Optional[int] = Query(None, description="Filter by league ID"),
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate the accuracy of predictions.
    """
    try:
        query = (
            select(
                func.count(models.Prediction.id).label('total_predictions'),
                func.sum(
                    case(
                        (
                            (models.Prediction.winner_team_id == models.Fixture.home_team_id) &
                            (models.Fixture.goals_home > models.Fixture.goals_away),
                            1
                        ),
                        (
                            (models.Prediction.winner_team_id == models.Fixture.away_team_id) &
                            (models.Fixture.goals_away > models.Fixture.goals_home),
                            1
                        ),
                        (
                            (models.Prediction.winner_team_id == None) &
                            (models.Fixture.goals_home == models.Fixture.goals_away),
                            1
                        ),
                        else_=0
                    )
                ).label('correct_predictions')
            )
            .select_from(models.Prediction)
            .join(models.Fixture, models.Prediction.fixture_id == models.Fixture.fixture_id)
            .where(models.Fixture.status_short == 'FT')
        )

        if league_id:
            query = query.where(models.Fixture.league_id == league_id)

        result = await db.execute(query)
        stats = result.first()

        total_predictions = stats.total_predictions or 0
        correct_predictions = stats.correct_predictions or 0
        accuracy = (correct_predictions / total_predictions) * 100 if total_predictions > 0 else 0

        return schemas.PredictionAccuracy(
            total_predictions=total_predictions,
            correct_predictions=correct_predictions,
            accuracy=accuracy
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
