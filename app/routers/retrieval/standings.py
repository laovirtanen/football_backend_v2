# app/routers/retrieval/standings.py

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import exists, select, func, case, and_, or_
from typing import List
from sqlalchemy.exc import SQLAlchemyError
import logging

from app import models, schemas
from app.database import get_db

router = APIRouter(
    prefix="/standings",
    tags=["standings"]
)

# Configure logger
logger = logging.getLogger(__name__)

@router.get("/{league_id}", response_model=List[schemas.TeamStanding])
async def get_league_standings(
    league_id: int,
    season_year: int,
    db: AsyncSession = Depends(get_db)
):
    try:
        # Build conditions for fixtures
        fixture_conditions = [
            models.Fixture.league_id == league_id,
            models.Fixture.season_year == season_year,
            models.Fixture.status_short == 'FT'
        ]

        # If Champions League (league_id=2) or Europa League (league_id=3), filter by League Stage
        # This is to exclude qualifying rounds and other stages
        # Still tbd if further developement will be done
        if league_id in [2, 3]:
            fixture_conditions.append(models.Fixture.round.ilike('League Stage%'))

        # Subquery for team statistics
        team_stats_subquery = (
            select(
                models.Team.team_id.label('team_id'),
                func.count(models.Fixture.fixture_id).filter(models.Fixture.status_short == 'FT').label('matches_played'),
                func.sum(
                    case(
                        (
                            and_(
                                models.Fixture.home_team_id == models.Team.team_id,
                                models.Fixture.goals_home > models.Fixture.goals_away
                            ),
                            1
                        ),
                        (
                            and_(
                                models.Fixture.away_team_id == models.Team.team_id,
                                models.Fixture.goals_away > models.Fixture.goals_home
                            ),
                            1
                        ),
                        else_=0
                    )
                ).label('wins'),
                func.sum(
                    case(
                        (
                            and_(
                                models.Fixture.goals_home == models.Fixture.goals_away,
                                or_(
                                    models.Fixture.home_team_id == models.Team.team_id,
                                    models.Fixture.away_team_id == models.Team.team_id
                                )
                            ),
                            1
                        ),
                        else_=0
                    )
                ).label('draws'),
                func.sum(
                    case(
                        (
                            and_(
                                models.Fixture.home_team_id == models.Team.team_id,
                                models.Fixture.goals_home < models.Fixture.goals_away
                            ),
                            1
                        ),
                        (
                            and_(
                                models.Fixture.away_team_id == models.Team.team_id,
                                models.Fixture.goals_away < models.Fixture.goals_home
                            ),
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
            .join(
                models.Fixture,
                or_(
                    models.Fixture.home_team_id == models.Team.team_id,
                    models.Fixture.away_team_id == models.Team.team_id
                )
            )
            .where(*fixture_conditions)
            .group_by(models.Team.team_id)
            .subquery()
        )

        # Calculate points and goal difference
        points = (team_stats_subquery.c.wins * 3 + team_stats_subquery.c.draws).label('points')
        goal_difference = (team_stats_subquery.c.goals_for - team_stats_subquery.c.goals_against).label('goal_difference')

        # Main standings query
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
            .join(team_stats_subquery, models.Team.team_id == team_stats_subquery.c.team_id)
            .join(models.TeamLeague, models.Team.team_id == models.TeamLeague.team_id)
            .where(
                models.TeamLeague.league_id == league_id,
                models.TeamLeague.season_year == season_year,
            )
            .order_by(
                points.desc(),
                goal_difference.desc(),
                team_stats_subquery.c.goals_for.desc()
            )
        )

        # Execute the query and fetch results
        result = await db.execute(standings_query)
        standings = result.fetchall()

        logger.debug(f"Fetched standings data: {standings}")

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

            try:
                team_data = schemas.TeamBase.model_validate(team)
            except Exception as parse_error:
                logger.error(f"Error parsing team data: {parse_error}", exc_info=True)
                raise HTTPException(status_code=500, detail="Error parsing team data.")

            standings_list.append(schemas.TeamStanding(
                rank=rank,
                team=team_data,
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

    except SQLAlchemyError as e:
        logger.error(f"Database error while fetching standings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database error occurred.")
    except Exception as e:
        logger.error(f"Unexpected error while fetching standings: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
