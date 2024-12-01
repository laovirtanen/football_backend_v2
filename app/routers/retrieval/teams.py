# app/routers/retrieval/teams.py

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, case, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
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
        result = await db.execute(
            select(models.Team).where(models.Team.team_id == team_id)
        )
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
        # Fetch team
        team_result = await db.execute(
            select(models.Team).where(models.Team.team_id == team_id)
        )
        team = team_result.scalar_one_or_none()
        if not team:
            raise HTTPException(status_code=404, detail="Team not found")

        # Fetch fixtures
        fixtures_query = select(models.Fixture).where(
            ((models.Fixture.home_team_id == team_id) | (models.Fixture.away_team_id == team_id)),
            models.Fixture.season_year == season_year,
            models.Fixture.status_short == 'FT'
        )
        fixtures_result = await db.execute(fixtures_query)
        fixtures = fixtures_result.scalars().all()

        if not fixtures:
            # Return zeroed statistics if no fixtures are found
            return schemas.TeamStatistics(
                team=schemas.TeamBase.model_validate(team),
                matches_played=0,
                wins=0,
                draws=0,
                losses=0,
                goals_for=0,
                goals_against=0,
                goal_difference=0,
                clean_sheets=0,
                average_shots_on_target=None,
                average_tackles=None,
                average_passes_accuracy=None
            )

        # Initialize stats
        matches_played = len(fixtures)
        wins = draws = losses = goals_for = goals_against = clean_sheets = 0
        total_shots_on_target = total_tackles = 0
        passes_accuracies = []

        # Fetch player statistics
        player_stats_query = select(models.PlayerStatistics).where(
            models.PlayerStatistics.team_id == team_id,
            models.PlayerStatistics.season_year == season_year
        )
        player_stats_result = await db.execute(player_stats_query)
        player_stats = player_stats_result.scalars().all()

        if player_stats:
            total_shots_on_target = sum(ps.shots_on or 0 for ps in player_stats)
            total_tackles = sum(ps.tackles_total or 0 for ps in player_stats)
            passes_accuracies = [ps.passes_accuracy for ps in player_stats if ps.passes_accuracy is not None]
        else:
            total_shots_on_target = total_tackles = 0
            passes_accuracies = []

        # Calculate statistics
        for fixture in fixtures:
            if fixture.home_team_id == team_id:
                gf = fixture.goals_home or 0
                ga = fixture.goals_away or 0
                is_clean_sheet = ga == 0
            else:
                gf = fixture.goals_away or 0
                ga = fixture.goals_home or 0
                is_clean_sheet = ga == 0

            goals_for += gf
            goals_against += ga

            if gf > ga:
                wins += 1
            elif gf < ga:
                losses += 1
            else:
                draws += 1

            if is_clean_sheet:
                clean_sheets += 1

        average_shots_on_target = (total_shots_on_target / matches_played) if matches_played > 0 else None
        average_tackles = (total_tackles / matches_played) if matches_played > 0 else None
        average_passes_accuracy = (sum(passes_accuracies) / len(passes_accuracies)) if passes_accuracies else None
        goal_difference = goals_for - goals_against

        return schemas.TeamStatistics(
            team=schemas.TeamBase.model_validate(team),
            matches_played=matches_played,
            wins=wins,
            draws=draws,
            losses=losses,
            goals_for=goals_for,
            goals_against=goals_against,
            goal_difference=goal_difference,
            clean_sheets=clean_sheets,
            average_shots_on_target=average_shots_on_target,
            average_tackles=average_tackles,
            average_passes_accuracy=average_passes_accuracy
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
