from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional

from app import models, schemas
from app.database import get_db

router = APIRouter(
    prefix="/player_statistics",
    tags=["player_statistics"]
)

@router.get("/", response_model=List[schemas.PlayerStatisticsBase])
async def get_player_statistics(
    player_id: Optional[int] = Query(None),
    league_id: Optional[int] = Query(None),
    season_year: Optional[int] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    try:
        query = select(models.PlayerStatistics)
        
        if player_id:
            query = query.where(models.PlayerStatistics.player_id == player_id)
        if league_id:
            query = query.where(models.PlayerStatistics.league_id == league_id)
        if season_year:
            query = query.where(models.PlayerStatistics.season_year == season_year)
        
        query = query.offset(offset).limit(limit)
        
        result = await db.execute(query)
        stats = result.scalars().all()
        return [schemas.PlayerStatisticsBase.model_validate(stat) for stat in stats]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
