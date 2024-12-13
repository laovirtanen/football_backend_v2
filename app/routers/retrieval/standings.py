# app/routers/retrieval/standings.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, case
from typing import List

from app import models, schemas
from app.database import get_db

router = APIRouter(
    prefix="/standings",
    tags=["standings"]
)

@router.get("/{league_id}", response_model=List[schemas.TeamStanding])
async def get_league_standings(
    league_id: int,
    season_year: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve the league standings for a specific league and season.
    """
    try:
        # Subquery to calculate team stats
        team_stats_subquery = (
            select(
                models.Team.team_id.label('team_id'),
                func.count().filter(models.Fixture.status_short == 'FT').label('matches_played'),
                func.sum(
                    case(
                        (
                            (models.Fixture.home_team_id == models.Team.team_id) & (models.Fixture.goals_home > models.Fixture.goals_away),
                            1
                        ),
                        (
                            (models.Fixture.away_team_id == models.Team.team_id) & (models.Fixture.goals_away > models.Fixture.goals_home),
                            1
                        ),
                        else_=0
                    )
                ).label('wins'),
                func.sum(
                    case(
                        (
                            (models.Fixture.goals_home == models.Fixture.goals_away) &
                            ((models.Fixture.home_team_id == models.Team.team_id) | (models.Fixture.away_team_id == models.Team.team_id)),
                            1
                        ),
                        else_=0
                    )
                ).label('draws'),
                func.sum(
                    case(
                        (
                            (models.Fixture.home_team_id == models.Team.team_id) & (models.Fixture.goals_home < models.Fixture.goals_away),
                            1
                        ),
                        (
                            (models.Fixture.away_team_id == models.Team.team_id) & (models.Fixture.goals_away < models.Fixture.goals_home),
                            1
                        ),
                        else_=0
                    )
                ).label('losses'),
                func.sum(
                    case(
                        (
                            models.Fixture.home_team_id == models.Team.team_id,
                            models.Fixture.goals_home
                        ),
                        (
                            models.Fixture.away_team_id == models.Team.team_id,
                            models.Fixture.goals_away
                        ),
                        else_=0
                    )
                ).label('goals_for'),
                func.sum(
                    case(
                        (
                            models.Fixture.home_team_id == models.Team.team_id,
                            models.Fixture.goals_away
                        ),
                        (
                            models.Fixture.away_team_id == models.Team.team_id,
                            models.Fixture.goals_home
                        ),
                        else_=0
                    )
                ).label('goals_against')
            )
            .select_from(models.Team)
            .join(models.Fixture, ((models.Fixture.home_team_id == models.Team.team_id) | (models.Fixture.away_team_id == models.Team.team_id)))
            .where(
                models.Team.league_id == league_id,
                models.Team.season_year == season_year,
                models.Fixture.status_short == 'FT',
                models.Fixture.league_id == league_id,
                models.Fixture.season_year == season_year
            )
            .group_by(models.Team.team_id)
            .subquery()
        )

        # Define labeled columns for ordering
        points = (team_stats_subquery.c.wins * 3 + team_stats_subquery.c.draws).label('points')
        goal_difference = (team_stats_subquery.c.goals_for - team_stats_subquery.c.goals_against).label('goal_difference')

        # Query to get standings
        standings_query = (
            select(
                models.Team,
                team_stats_subquery.c.matches_played,
                team_stats_subquery.c.wins,
                team_stats_subquery.c.draws,
                team_stats_subquery.c.losses,
                team_stats_subquery.c.goals_for,
                team_stats_subquery.c.goals_against,
                points,
                goal_difference
            )
            .outerjoin(team_stats_subquery, models.Team.team_id == team_stats_subquery.c.team_id)
            .where(
                models.Team.league_id == league_id,
                models.Team.season_year == season_year
            )
            .order_by(
                points.desc(),
                goal_difference.desc(),
                team_stats_subquery.c.goals_for.desc()
            )
        )

        result = await db.execute(standings_query)
        standings = result.fetchall()

        # Build the standings list
        standings_list = []
        rank = 1
        for row in standings:
            team = row[0]
            matches_played = row[1] or 0
            wins = row[2] or 0
            draws = row[3] or 0
            losses = row[4] or 0
            goals_for = row[5] or 0
            goals_against = row[6] or 0
            points_value = row[7] or 0
            goal_diff_value = row[8] or 0
            standings_list.append(schemas.TeamStanding(
                rank=rank,
                team=schemas.TeamBase.model_validate(team),
                matches_played=matches_played,
                points=points_value,
                wins=wins,
                draws=draws,
                losses=losses,
                goals_for=goals_for,
                goals_against=goals_against,
                goal_difference=goal_diff_value
            ))
            rank += 1

        return standings_list

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
