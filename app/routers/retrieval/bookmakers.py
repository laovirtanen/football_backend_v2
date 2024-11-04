# app/routers/retrieval/bookmakers.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional

from app import models, schemas
from app.database import get_db

router = APIRouter(
    prefix="/bookmakers",
    tags=["bookmakers"]
)

@router.get("/", response_model=List[schemas.BookmakerSchema])
async def get_bookmakers(
    db: AsyncSession = Depends(get_db),
    search: Optional[str] = Query(None, min_length=3, max_length=100),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Retrieve a list of bookmakers with optional search.
    """
    try:
        query = select(models.Bookmaker)
        if search:
            query = query.where(models.Bookmaker.name.ilike(f"%{search}%"))
        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        bookmakers = result.scalars().all()
        return bookmakers
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{bookmaker_id}", response_model=schemas.BookmakerSchema)
async def get_bookmaker_by_id(
    bookmaker_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a specific bookmaker by its ID.
    """
    try:
        result = await db.execute(select(models.Bookmaker).where(models.Bookmaker.id == bookmaker_id))
        bookmaker = result.scalar_one_or_none()
        if not bookmaker:
            raise HTTPException(status_code=404, detail="Bookmaker not found")
        return bookmaker
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
