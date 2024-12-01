# app/routers/retrieval/fixtures.py

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import Date, cast, func, desc, case, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from datetime import datetime, timedelta, timezone

from app import models, schemas
from app.database import get_db

import logging

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/fixtures",
    tags=["fixtures"]
)


@router.get("/", response_model=List[schemas.FixtureBaseDetailed])
async def get_fixtures(
    db: AsyncSession = Depends(get_db),
    league_id: Optional[int] = Query(None, description="Filter by league ID"),
    team_id: Optional[int] = Query(None, description="Filter by team ID (home or away)"),
    season_year: Optional[int] = Query(None, description="Filter by season year"),
    date_from: Optional[datetime] = Query(None, description="Start date in YYYY-MM-DD format"),
    date_to: Optional[datetime] = Query(None, description="End date in YYYY-MM-DD format"),
    status: Optional[str] = Query(None, description="Filter by match status"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    try:
        logger.info("Fetching fixtures with filters: league_id=%s, team_id=%s, season_year=%s, date_from=%s, date_to=%s, status=%s, limit=%s, offset=%s",
                    league_id, team_id, season_year, date_from, date_to, status, limit, offset)

        fixture_ids_query = select(models.Fixture.fixture_id)

        if league_id:
            fixture_ids_query = fixture_ids_query.where(models.Fixture.league_id == league_id)
        if team_id:
            fixture_ids_query = fixture_ids_query.where(
                (models.Fixture.home_team_id == team_id) |
                (models.Fixture.away_team_id == team_id)
            )
        if season_year:
            fixture_ids_query = fixture_ids_query.where(models.Fixture.season_year == season_year)

        if date_from and date_to and date_from.date() == date_to.date():
            date_only = date_from.date()
            fixture_ids_query = fixture_ids_query.where(
                cast(models.Fixture.date, Date) == date_only
            )
        else:
            if date_from:
                fixture_ids_query = fixture_ids_query.where(
                    cast(models.Fixture.date, Date) >= date_from.date()
                )
            if date_to:
                fixture_ids_query = fixture_ids_query.where(
                    cast(models.Fixture.date, Date) <= date_to.date()
                )

        if status:
            fixture_ids_query = fixture_ids_query.where(models.Fixture.status_short.ilike(f"%{status}%"))

        fixture_ids_query = fixture_ids_query.offset(offset).limit(limit)

        logger.debug("Executing Fixture IDs Query: %s", fixture_ids_query)

        # Execute the query to get fixture IDs
        result = await db.execute(fixture_ids_query)
        fixture_ids = result.scalars().all()

        logger.info("Found %d fixtures matching filters.", len(fixture_ids))

        if not fixture_ids:
            logger.info("No fixtures found for the given filters.")
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

        logger.debug("Executing Fixtures Query: %s", fixtures_query)

        fixtures_result = await db.execute(fixtures_query)
        fixtures = fixtures_result.scalars().all()

        logger.info("Returning %d fixtures with detailed information.", len(fixtures))
        return fixtures
    except Exception as e:
        logger.error("Error fetching fixtures: %s", e)
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{fixture_id}/detailed", response_model=schemas.FixtureDetailedResponse)
async def get_detailed_fixture(
    fixture_id: int = Path(..., description="The ID of the fixture to retrieve"),
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve detailed information for a specific fixture, including comprehensive statistics.
    """
    try:
        logger.info("Fetching detailed fixture for fixture_id: %s", fixture_id)

        # Fetch the fixture with related data
        fixture_query = select(models.Fixture).where(models.Fixture.fixture_id == fixture_id).options(
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
        fixture_result = await db.execute(fixture_query)
        fixture = fixture_result.scalar_one_or_none()
        if not fixture:
            logger.warning(f"Fixture with id {fixture_id} not found.")
            raise HTTPException(status_code=404, detail="Fixture not found")

        logger.info(f"Fixture fetched: {fixture.fixture_id}")

        # Gather additional data
        home_team_id = fixture.home_team_id
        away_team_id = fixture.away_team_id
        season_year = fixture.season_year

        logger.info(f"Home Team ID: {home_team_id}, Away Team ID: {away_team_id}, Season Year: {season_year}")

        # Head-to-Head Stats
        time_range = datetime.now(timezone.utc) - timedelta(days=365 * 5)
        recent_matches_limit = 5

        h2h_query = select(models.Fixture).where(
            (
                (models.Fixture.home_team_id == home_team_id) & (models.Fixture.away_team_id == away_team_id)
            ) | (
                (models.Fixture.home_team_id == away_team_id) & (models.Fixture.away_team_id == home_team_id)
            ),
            models.Fixture.status_short == 'FT',
            models.Fixture.date >= time_range
        ).order_by(desc(models.Fixture.date)).limit(recent_matches_limit).options(
            selectinload(models.Fixture.home_team),
            selectinload(models.Fixture.away_team)
        )

        logger.debug("Executing Head-to-Head Query: %s", h2h_query)
        h2h_result = await db.execute(h2h_query)
        h2h_fixtures = h2h_result.scalars().all()
        logger.info(f"Found {len(h2h_fixtures)} head-to-head fixtures.")

        h2h_stats = await calculate_h2h_stats(h2h_fixtures, home_team_id, away_team_id)
        logger.debug(f"H2H Stats: {h2h_stats}")

        # Recent Form for Both Teams
        home_recent_form = await get_team_recent_form(db, home_team_id, recent_matches_limit)
        away_recent_form = await get_team_recent_form(db, away_team_id, recent_matches_limit)
        logger.debug(f"Home Recent Form: {home_recent_form}")
        logger.debug(f"Away Recent Form: {away_recent_form}")

        # Team Statistics
        home_team_stats = await get_team_statistics(db, home_team_id, season_year)
        away_team_stats = await get_team_statistics(db, away_team_id, season_year)
        logger.debug(f"Home Team Stats: {home_team_stats}")
        logger.debug(f"Away Team Stats: {away_team_stats}")

        # Top Players (e.g., Top Scorers)
        home_top_players = await get_top_players(db, home_team_id, season_year)
        away_top_players = await get_top_players(db, away_team_id, season_year)
        logger.debug(f"Home Top Players: {home_top_players}")
        logger.debug(f"Away Top Players: {away_top_players}")

        # Serialize the base fixture data
        fixture_base = schemas.FixtureBaseDetailed.model_validate(fixture, from_attributes=True).model_dump()

        # Assemble the complete data for FixtureDetailedResponse
        detailed_fixture_data = fixture_base.copy()
        detailed_fixture_data.update({
            'h2h_stats': h2h_stats,  # Pass the model instance directly
            'home_recent_form': home_recent_form,  # Pass the list of models directly
            'away_recent_form': away_recent_form,
            'home_team_stats': home_team_stats,
            'away_team_stats': away_team_stats,
            'home_top_players': home_top_players,
            'away_top_players': away_top_players,
        })

        logger.info("Assembling FixtureDetailedResponse.")
        # Validate and create the FixtureDetailedResponse instance
        detailed_fixture = schemas.FixtureDetailedResponse(**detailed_fixture_data)

        logger.info("FixtureDetailedResponse constructed successfully.")
        return detailed_fixture

    except Exception as e:
        logger.error("Error fetching detailed fixture: %s", e)
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# Helper Functions

async def calculate_h2h_stats(fixtures: List[models.Fixture], home_team_id: int, away_team_id: int) -> schemas.FixtureH2HStats:
    total_matches = len(fixtures)
    home_wins = 0
    away_wins = 0
    draws = 0
    recent_matches_list = []

    for fixture in fixtures:
        if fixture.goals_home is None or fixture.goals_away is None:
            continue  # Skip if scores are missing

        if fixture.home_team_id == home_team_id:
            gf = fixture.goals_home or 0
            ga = fixture.goals_away or 0
            opponent_name = fixture.away_team.name
            home_or_away = 'Home'
        else:
            gf = fixture.goals_away or 0
            ga = fixture.goals_home or 0
            opponent_name = fixture.home_team.name
            home_or_away = 'Away'

        if gf > ga:
            outcome = 'W'
            if fixture.home_team_id == home_team_id:
                home_wins += 1
            else:
                away_wins += 1
        elif gf < ga:
            outcome = 'L'
            if fixture.home_team_id == home_team_id:
                away_wins += 1
            else:
                home_wins += 1
        else:
            outcome = 'D'
            draws += 1

        recent_match = schemas.TeamRecentForm(
            fixture_id=fixture.fixture_id,
            date=fixture.date,
            opponent=opponent_name,
            home_or_away=home_or_away,
            goals_for=gf,
            goals_against=ga,
            outcome=outcome
        )
        recent_matches_list.append(recent_match)

    h2h_stats = schemas.FixtureH2HStats(
        total_matches=total_matches,
        home_team_wins=home_wins,
        away_team_wins=away_wins,
        draws=draws,
        recent_matches=recent_matches_list
    )

    return h2h_stats


# In fixtures.py

async def get_team_recent_form(db: AsyncSession, team_id: int, limit: int = 15) -> List[schemas.TeamRecentForm]:
    recent_fixtures_query = select(models.Fixture).where(
        or_(
            models.Fixture.home_team_id == team_id,
            models.Fixture.away_team_id == team_id
        ),
        models.Fixture.status_short == 'FT'
    ).order_by(desc(models.Fixture.date)).limit(limit).options(
        selectinload(models.Fixture.home_team),
        selectinload(models.Fixture.away_team)
    )

    logger.debug("Executing Recent Form Query for team_id: %s with limit: %s", team_id, limit)
    result = await db.execute(recent_fixtures_query)
    fixtures = result.scalars().all()
    recent_form = []

    for fixture in fixtures:
        if fixture.home_team_id == team_id:
            goals_for = fixture.goals_home
            goals_against = fixture.goals_away
            opponent_name = fixture.away_team.name
            opponent_logo = fixture.away_team.logo
            opponent_team_id = fixture.away_team.team_id
            home_or_away = 'Home'
        else:
            goals_for = fixture.goals_away
            goals_against = fixture.goals_home
            opponent_name = fixture.home_team.name
            opponent_logo = fixture.home_team.logo
            opponent_team_id = fixture.home_team.team_id
            home_or_away = 'Away'

        if goals_for > goals_against:
            outcome = 'W'
        elif goals_for < goals_against:
            outcome = 'L'
        else:
            outcome = 'D'

        recent_match = schemas.TeamRecentForm(
            fixture_id=fixture.fixture_id,
            date=fixture.date,
            opponent=opponent_name,
            opponent_logo=opponent_logo,
            opponent_team_id=opponent_team_id,
            home_or_away=home_or_away,
            goals_for=goals_for,
            goals_against=goals_against,
            outcome=outcome
        )
        recent_form.append(recent_match)

    logger.debug(f"Recent form for team_id {team_id}: {recent_form}")
    return recent_form



async def get_team_statistics(db: AsyncSession, team_id: int, season_year: int) -> schemas.TeamStatistics:
    logger.debug("Fetching team statistics for team_id: %s, season_year: %s", team_id, season_year)

    # Fetch fixtures where the team played
    fixtures_query = select(models.Fixture.fixture_id).where(
        or_(
            models.Fixture.home_team_id == team_id,
            models.Fixture.away_team_id == team_id
        ),
        models.Fixture.season_year == season_year,
        models.Fixture.status_short == 'FT'
    )
    result = await db.execute(fixtures_query)
    fixture_ids = [row[0] for row in result.fetchall()]

    matches_played = len(fixture_ids)
    logger.info("Matches played: %s", matches_played)
    if matches_played == 0:
        # Return zeroed statistics if no matches found
        team_stats = schemas.TeamStatistics(
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
        logger.debug("No matches found. Returning zeroed TeamStatistics.")
        return team_stats

    # Fetch goals and results
    fixtures_query = select(models.Fixture).where(
        models.Fixture.fixture_id.in_(fixture_ids)
    ).options(
        selectinload(models.Fixture.home_team),
        selectinload(models.Fixture.away_team)
    )
    result = await db.execute(fixtures_query)
    fixtures = result.scalars().all()

    wins = draws = losses = goals_for = goals_against = clean_sheets = 0
    total_shots_on_target = total_tackles = 0
    passes_accuracies = []

    # Fetch player statistics for these fixtures
    player_stats_query = select(models.PlayerStatistics).where(
        models.PlayerStatistics.team_id == team_id,
        models.PlayerStatistics.season_year == season_year
        # Add any additional filters if needed
    )
    result = await db.execute(player_stats_query)
    player_stats = result.scalars().all()

    # Aggregate player statistics
    total_shots_on_target = sum(ps.shots_on or 0 for ps in player_stats)
    total_tackles = sum(ps.tackles_total or 0 for ps in player_stats)
    passes_accuracies = [ps.passes_accuracy for ps in player_stats if ps.passes_accuracy is not None]

    logger.debug(f"Total shots on target: {total_shots_on_target}, Total tackles: {total_tackles}, Pass accuracies: {passes_accuracies}")

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

    if matches_played > 0:
        average_shots_on_target = total_shots_on_target / matches_played
        average_tackles = total_tackles / matches_played
        average_passes_accuracy = sum(passes_accuracies) / len(passes_accuracies) if passes_accuracies else None
    else:
        average_shots_on_target = None
        average_tackles = None
        average_passes_accuracy = None

    goal_difference = goals_for - goals_against

    team_stats = schemas.TeamStatistics(
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

    logger.debug(f"Team statistics: {team_stats}")
    return team_stats


async def get_top_players(
    db: AsyncSession, team_id: int, season_year: int, limit: int = 5
) -> List[schemas.TopPlayer]:
    logger.debug(
        "Fetching top players for team_id: %s, season_year: %s, limit: %s",
        team_id,
        season_year,
        limit,
    )

    stmt = (
        select(
            models.PlayerStatistics.player_id,
            models.Player.name,
            models.PlayerStatistics.position,
            func.coalesce(func.sum(models.PlayerStatistics.goals_total), 0).label("goals"),
            models.Player.photo,  # Include photo
        )
        .join(
            models.Player,
            models.Player.player_id == models.PlayerStatistics.player_id,
        )
        .where(
            models.PlayerStatistics.team_id == team_id,
            models.PlayerStatistics.season_year == season_year,
        )
        .group_by(
            models.PlayerStatistics.player_id,
            models.Player.name,
            models.PlayerStatistics.position,
            models.Player.photo,  # Include photo in group_by
        )
        .order_by(desc("goals"))
        .limit(limit)
    )

    logger.debug("Executing Top Players Query: %s", stmt)
    result = await db.execute(stmt)
    players = result.fetchall()

    top_players = []
    for row in players:
        top_player = schemas.TopPlayer(
            player_id=row.player_id,
            name=row.name,
            position=row.position,
            goals=row.goals,  # Now guaranteed to be an int
            photo=row.photo,  # Include photo
        )
        top_players.append(top_player)

    logger.debug(f"Top players: {top_players}")
    return top_players