# app/routers/retrieval/fixtures.py

from datetime import date, datetime
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Date, cast, desc, func, select, or_
from sqlalchemy.orm import selectinload
from app.database import get_db
from app import models, schemas

router = APIRouter(
    prefix="/fixtures",
    tags=["fixtures"]
)

logger = logging.getLogger(__name__)

@router.get("/", response_model=List[schemas.FixtureBase])
async def get_fixtures(
    league_id: int = Query(..., description="ID of the league"),
    season_year: int = Query(..., description="Season year"),
    date_from: Optional[date] = Query(None, description="Start date in YYYY-MM-DD format"),
    date_to: Optional[date] = Query(None, description="End date in YYYY-MM-DD format"),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"Fetching fixtures with league_id={league_id}, season_year={season_year}, date_from={date_from}, date_to={date_to}")
    try:
        # Initialize the query
        query = select(models.Fixture).where(
            models.Fixture.league_id == league_id,
            models.Fixture.season_year == season_year
        ).options(
            selectinload(models.Fixture.home_team),
            selectinload(models.Fixture.away_team),
            selectinload(models.Fixture.league),
            selectinload(models.Fixture.venue),
            selectinload(models.Fixture.prediction),
            selectinload(models.Fixture.match_events),
            selectinload(models.Fixture.match_statistics),
            selectinload(models.Fixture.odds)
                .selectinload(models.FixtureOdds.fixture_bookmakers)
                .selectinload(models.FixtureBookmaker.bookmaker),
            # Load bets and their bet_types
            selectinload(models.Fixture.odds)
                .selectinload(models.FixtureOdds.fixture_bookmakers)
                .selectinload(models.FixtureBookmaker.bets)
                .selectinload(models.Bet.bet_type),
            # Load bets and their odd_values
            selectinload(models.Fixture.odds)
                .selectinload(models.FixtureOdds.fixture_bookmakers)
                .selectinload(models.FixtureBookmaker.bets)
                .selectinload(models.Bet.odd_values),
        )

        # Apply date filters
        if date_from and date_to and date_from == date_to:
            # When both dates are the same
            query = query.where(cast(models.Fixture.date, Date) == date_from)
        else:
            if date_from:
                query = query.where(cast(models.Fixture.date, Date) >= date_from)
            if date_to:
                query = query.where(cast(models.Fixture.date, Date) <= date_to)

        result = await db.execute(query)
        fixtures = result.scalars().all()

        if not fixtures:
            logger.warning("No fixtures found for the given parameters.")
            return []

        return fixtures

    except Exception as e:
        logger.error(f"Error fetching fixtures: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

@router.get("/{fixture_id}/detailed", response_model=schemas.FixtureDetailedResponse)
async def get_detailed_fixture(
    fixture_id: int = Path(..., description="The ID of the fixture to retrieve"),
    db: AsyncSession = Depends(get_db)
):
    logger.info(f"Fetching detailed fixture for fixture_id: {fixture_id}")

    # Fetch the fixture with related data
    fixture_query = select(models.Fixture).where(models.Fixture.fixture_id == fixture_id).options(
        selectinload(models.Fixture.home_team),
        selectinload(models.Fixture.away_team),
        selectinload(models.Fixture.league),
        selectinload(models.Fixture.venue),
        selectinload(models.Fixture.prediction),
        selectinload(models.Fixture.match_events),
        selectinload(models.Fixture.match_statistics),
        selectinload(models.Fixture.odds).options(
            selectinload(models.FixtureOdds.fixture_bookmakers).options(
                selectinload(models.FixtureBookmaker.bookmaker),
                selectinload(models.FixtureBookmaker.bets).options(
                    selectinload(models.Bet.bet_type),
                    selectinload(models.Bet.odd_values),
                ),
            ),
        ),
    )
    fixture_result = await db.execute(fixture_query)
    fixture = fixture_result.scalar_one_or_none()
    if not fixture:
        logger.warning(f"Fixture with id {fixture_id} not found.")
        raise HTTPException(status_code=404, detail="Fixture not found")

    # Prepare detailed fixture data
    detailed_fixture_data = schemas.FixtureBaseDetailed.model_validate(fixture, from_attributes=True).model_dump()

    # Process match events
    match_events = []
    if fixture.match_events:
        for event in fixture.match_events:
            match_event = schemas.MatchEvent.model_validate(event, from_attributes=True).model_dump()
            match_events.append(match_event)
    detailed_fixture_data['match_events'] = match_events

    # Process match statistics
    match_statistics = {}
    if fixture.match_statistics:
        for stat in fixture.match_statistics:
            stats_dict = schemas.MatchStatistics.model_validate(stat, from_attributes=True).model_dump()
            team_id = stats_dict['team_id']
            if team_id == fixture.home_team_id:
                match_statistics['home'] = {item['type']: item['value'] for item in stats_dict['statistics']}
            elif team_id == fixture.away_team_id:
                match_statistics['away'] = {item['type']: item['value'] for item in stats_dict['statistics']}
    detailed_fixture_data['match_statistics'] = match_statistics

    # Include odds if available
    if fixture.odds:
        detailed_fixture_data['odds'] = schemas.FixtureOddsSchema.model_validate(fixture.odds, from_attributes=True).model_dump()

    # Include prediction if available
    if fixture.prediction:
        detailed_fixture_data['prediction'] = schemas.PredictionSchema.model_validate(fixture.prediction, from_attributes=True).model_dump()

    # Fetch head-to-head stats
    h2h_stats = await get_h2h_stats(db, fixture.home_team_id, fixture.away_team_id)

    # Fetch recent form for both teams
    home_recent_form = await get_team_recent_form(db, fixture.home_team_id)
    away_recent_form = await get_team_recent_form(db, fixture.away_team_id)

    # Fetch team statistics
    season_year = fixture.season_year
    home_team_stats = await get_team_statistics(db, fixture.home_team_id, season_year)
    away_team_stats = await get_team_statistics(db, fixture.away_team_id, season_year)

    # Fetch top players
    home_top_players = await get_top_players(db, fixture.home_team_id, season_year)
    away_top_players = await get_top_players(db, fixture.away_team_id, season_year)

    # Include additional data in the response
    detailed_fixture_data.update({
        'h2h_stats': h2h_stats.model_dump(),
        'home_recent_form': [form.model_dump() for form in home_recent_form],
        'away_recent_form': [form.model_dump() for form in away_recent_form],
        'home_team_stats': home_team_stats.model_dump(),
        'away_team_stats': away_team_stats.model_dump(),
        'home_top_players': [player.model_dump() for player in home_top_players],
        'away_top_players': [player.model_dump() for player in away_top_players],
    })

    detailed_fixture_response = schemas.FixtureDetailedResponse(**detailed_fixture_data)

    logger.info(f"Returning detailed fixture for fixture_id: {fixture_id}")
    return detailed_fixture_response

async def get_h2h_stats(db: AsyncSession, home_team_id: int, away_team_id: int) -> schemas.FixtureH2HStats:
    logger.debug(f"Fetching H2H stats for home_team_id: {home_team_id}, away_team_id: {away_team_id}")

    h2h_query = select(models.Fixture).where(
        or_(
            (models.Fixture.home_team_id == home_team_id) & (models.Fixture.away_team_id == away_team_id),
            (models.Fixture.home_team_id == away_team_id) & (models.Fixture.away_team_id == home_team_id)
        ),
        models.Fixture.status_short == 'FT'
    ).order_by(models.Fixture.date.desc()).limit(5).options(
        selectinload(models.Fixture.home_team),
        selectinload(models.Fixture.away_team)
    )

    result = await db.execute(h2h_query)
    fixtures = result.scalars().all()

    total_matches = len(fixtures)
    home_team_wins = away_team_wins = draws = 0
    recent_matches = []

    for fixture in fixtures:
        if fixture.goals_home is None or fixture.goals_away is None:
            continue

        if fixture.goals_home > fixture.goals_away:
            if fixture.home_team_id == home_team_id:
                home_team_wins += 1
            else:
                away_team_wins += 1
        elif fixture.goals_home < fixture.goals_away:
            if fixture.away_team_id == home_team_id:
                home_team_wins += 1
            else:
                away_team_wins += 1
        else:
            draws += 1

        recent_match = {
            'fixture_id': fixture.fixture_id,
            'date': fixture.date,
            'home_team': fixture.home_team.name,
            'away_team': fixture.away_team.name,
            'goals_home': fixture.goals_home,
            'goals_away': fixture.goals_away
        }
        recent_matches.append(recent_match)

    h2h_stats = schemas.FixtureH2HStats(
        total_matches=total_matches,
        home_team_wins=home_team_wins,
        away_team_wins=away_team_wins,
        draws=draws,
        recent_matches=recent_matches
    )

    return h2h_stats

async def get_team_recent_form(db: AsyncSession, team_id: int, limit: int = 15) -> List[schemas.TeamRecentForm]:
    recent_fixtures_query = select(models.Fixture).where(
        or_(
            models.Fixture.home_team_id == team_id,
            models.Fixture.away_team_id == team_id
        ),
        models.Fixture.status_short == 'FT'
    ).order_by(models.Fixture.date.desc()).limit(limit).options(
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
