# app/routers/retrieval/predictions.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
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
        return predictions
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
        return prediction
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
