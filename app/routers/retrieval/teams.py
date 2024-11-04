# app/routers/retrieval/teams.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional

from app import models, schemas
from app.database import get_db

router = APIRouter(
    prefix="/teams",
    tags=["teams"]
)

@router.get("/", response_model=List[schemas.TeamBase])
async def get_teams(
    db: AsyncSession = Depends(get_db),
    league_id: Optional[int] = Query(None, description="Filter by league ID"),
    season_year: Optional[int] = Query(None, description="Filter by season year"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    Retrieve a list of teams with optional filters.
    """
    try:
        query = select(models.Team)
        if league_id:
            query = query.where(models.Team.league_id == league_id)
        if season_year:
            query = query.where(models.Team.season_year == season_year)
        query = query.offset(offset).limit(limit)
        result = await db.execute(query)
        teams = result.scalars().all()
        return [schemas.TeamBase.model_validate(team) for team in teams]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{team_id}", response_model=schemas.TeamBase)
async def get_team_by_id(
    team_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a specific team by its ID.
    """
    try:
        result = await db.execute(select(models.Team).where(models.Team.team_id == team_id))
        team = result.scalar_one_or_none()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")
        return schemas.TeamBase.model_validate(team)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{team_id}/statistics", response_model=schemas.TeamStatistics)
async def get_team_statistics(
    team_id: int,
    season_year: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve aggregated statistics for a specific team.
    """
    try:
        # Calculate team statistics
        stats_query = (
            select(
                func.count().filter(models.Fixture.status_short == 'FT').label('matches_played'),
                func.sum(
                    case(
                        (
                            (models.Fixture.home_team_id == team_id) & (models.Fixture.goals_home > models.Fixture.goals_away),
                            1
                        ),
                        (
                            (models.Fixture.away_team_id == team_id) & (models.Fixture.goals_away > models.Fixture.goals_home),
                            1
                        ),
                        else_=0
                    )
                ).label('wins'),
                func.sum(
                    case(
                        (
                            (models.Fixture.goals_home == models.Fixture.goals_away) &
                            ((models.Fixture.home_team_id == team_id) | (models.Fixture.away_team_id == team_id)),
                            1
                        ),
                        else_=0
                    )
                ).label('draws'),
                func.sum(
                    case(
                        (
                            (models.Fixture.home_team_id == team_id) & (models.Fixture.goals_home < models.Fixture.goals_away),
                            1
                        ),
                        (
                            (models.Fixture.away_team_id == team_id) & (models.Fixture.goals_away < models.Fixture.goals_home),
                            1
                        ),
                        else_=0
                    )
                ).label('losses'),
                func.sum(
                    case(
                        (
                            models.Fixture.home_team_id == team_id,
                            models.Fixture.goals_home
                        ),
                        (
                            models.Fixture.away_team_id == team_id,
                            models.Fixture.goals_away
                        ),
                        else_=0
                    )
                ).label('goals_for'),
                func.sum(
                    case(
                        (
                            models.Fixture.home_team_id == team_id,
                            models.Fixture.goals_away
                        ),
                        (
                            models.Fixture.away_team_id == team_id,
                            models.Fixture.goals_home
                        ),
                        else_=0
                    )
                ).label('goals_against')
            )
            .select_from(models.Fixture)
            .where(
                ((models.Fixture.home_team_id == team_id) | (models.Fixture.away_team_id == team_id)),
                models.Fixture.season_year == season_year,
                models.Fixture.status_short == 'FT'
            )
        )

        result = await db.execute(stats_query)
        stats = result.first()

        team_result = await db.execute(select(models.Team).where(models.Team.team_id == team_id))
        team = team_result.scalar_one_or_none()

        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        return schemas.TeamStatistics(
            team=schemas.TeamBase.model_validate(team),
            matches_played=stats.matches_played or 0,
            wins=stats.wins or 0,
            draws=stats.draws or 0,
            losses=stats.losses or 0,
            goals_for=stats.goals_for or 0,
            goals_against=stats.goals_against or 0,
            goal_difference=(stats.goals_for or 0) - (stats.goals_against or 0)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
