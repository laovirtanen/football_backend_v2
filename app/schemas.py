from __future__ import annotations
from pydantic import BaseModel, ConfigDict
from typing import Dict, Optional, Any, List
from datetime import date, datetime

class BookmakerSchema(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class BetTypeSchema(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class OddValueSchema(BaseModel):
    id: int
    value: str
    odd: str

    model_config = ConfigDict(from_attributes=True)


class BetSchema(BaseModel):
    id: int
    bet_type: BetTypeSchema
    odd_values: List[OddValueSchema]

    model_config = ConfigDict(from_attributes=True)


class FixtureBookmakerSchema(BaseModel):
    id: int
    bookmaker: BookmakerSchema
    bets: List[BetSchema]

    model_config = ConfigDict(from_attributes=True)

class FixtureOddsSchema(BaseModel):
    id: int
    update_time: datetime
    fixture_id: int
    fixture_bookmakers: List[FixtureBookmakerSchema]

    model_config = ConfigDict(from_attributes=True)

class LeagueBase(BaseModel):
    league_id: int
    name: str
    type: Optional[str]
    logo: Optional[str]
    country_name: Optional[str]
    country_code: Optional[str]
    country_flag: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class SeasonBase(BaseModel):
    id: int
    league_id: int
    year: int
    start: Optional[date]
    end: Optional[date]
    current: bool
    coverage: Optional[Any] = None

    model_config = ConfigDict(from_attributes=True)

class TeamBase(BaseModel):
    team_id: int
    name: str
    code: Optional[str]
    country: Optional[str]
    founded: Optional[int]
    national: Optional[bool]
    logo: Optional[str]
    league_id: int
    season_year: int

    model_config = ConfigDict(from_attributes=True)


class PlayerBase(BaseModel):
    player_id: int
    name: str
    firstname: Optional[str]
    lastname: Optional[str]
    age: Optional[int]
    birth_date: Optional[date]
    birth_place: Optional[str]
    birth_country: Optional[str]
    nationality: Optional[str]
    height: Optional[str]
    weight: Optional[str]
    injured: Optional[bool]
    photo: Optional[str]
    team_id: int
    season_year: int
    team: Optional[TeamBase]

    model_config = ConfigDict(from_attributes=True)


class PlayerStatisticsBase(BaseModel):
    id: int
    player_id: int
    team_id: int
    league_id: int
    season_year: int

    # Game statistics
    appearances: Optional[int]
    lineups: Optional[int]
    minutes: Optional[int]
    number: Optional[int]
    position: Optional[str]
    rating: Optional[float]
    captain: Optional[bool]

    # Substitute statistics
    subs_in: Optional[int]
    subs_out: Optional[int]
    subs_bench: Optional[int]

    # Shots statistics
    shots_total: Optional[int]
    shots_on: Optional[int]

    # Goals statistics
    goals_total: Optional[int]
    goals_conceded: Optional[int]
    goals_assists: Optional[int]
    goals_saves: Optional[int]

    # Passes statistics
    passes_total: Optional[int]
    passes_key: Optional[int]
    passes_accuracy: Optional[int]

    # Tackles statistics
    tackles_total: Optional[int]
    tackles_blocks: Optional[int]
    tackles_interceptions: Optional[int]

    # Duels statistics
    duels_total: Optional[int]
    duels_won: Optional[int]

    # Dribbles statistics
    dribbles_attempts: Optional[int]
    dribbles_success: Optional[int]
    dribbles_past: Optional[int]

    # Fouls statistics
    fouls_drawn: Optional[int]
    fouls_committed: Optional[int]

    # Cards statistics
    cards_yellow: Optional[int]
    cards_yellowred: Optional[int]
    cards_red: Optional[int]

    # Penalty statistics
    penalty_won: Optional[int]
    penalty_committed: Optional[int]
    penalty_scored: Optional[int]
    penalty_missed: Optional[int]
    penalty_saved: Optional[int]

    model_config = ConfigDict(from_attributes=True)


class VenueBase(BaseModel):
    id: Optional[int] = None
    name: Optional[str]
    city: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class FixtureBase(BaseModel):
    fixture_id: int
    referee: Optional[str]
    timezone: str
    date: datetime
    timestamp: int
    venue_id: Optional[int]
    status_long: str
    status_short: str
    status_elapsed: Optional[int]
    status_extra: Optional[str]
    league_id: int
    home_team: 'TeamBase'  # Include home_team
    away_team: 'TeamBase'  # Include away_team
    season_year: int
    round: Optional[str]
    home_team_id: int
    away_team_id: int
    goals_home: Optional[int]
    goals_away: Optional[int]
    score_halftime_home: Optional[int]
    score_halftime_away: Optional[int]
    score_fulltime_home: Optional[int]
    score_fulltime_away: Optional[int]
    score_extratime_home: Optional[int]
    score_extratime_away: Optional[int]
    score_penalty_home: Optional[int]
    score_penalty_away: Optional[int]
    odds: Optional[FixtureOddsSchema] = None

    model_config = ConfigDict(from_attributes=True)



class PredictionBase(BaseModel):
    fixture_id: int
    winner_team_id: Optional[int] = None
    win_or_draw: Optional[bool] = None
    under_over: Optional[str] = None
    goals_home: Optional[str] = None
    goals_away: Optional[str] = None
    advice: Optional[str] = None
    percent_home: Optional[str] = None
    percent_draw: Optional[str] = None
    percent_away: Optional[str] = None
    comparison: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)


class LeagueWithTeams(LeagueBase):
    teams: List[TeamBase] = []

    model_config = ConfigDict(from_attributes=True)




class FixtureBaseDetailed(BaseModel):
    fixture_id: int
    referee: Optional[str]
    timezone: str
    date: datetime
    timestamp: int
    venue: Optional[VenueBase]
    status_long: str
    status_short: str
    status_elapsed: Optional[int]
    status_extra: Optional[str]
    league: LeagueBase
    season_year: int
    round: Optional[str]
    home_team: TeamBase
    away_team: TeamBase
    goals_home: Optional[int]
    goals_away: Optional[int]
    score_halftime_home: Optional[int]
    score_halftime_away: Optional[int]
    score_fulltime_home: Optional[int]
    score_fulltime_away: Optional[int]
    score_extratime_home: Optional[int]
    score_extratime_away: Optional[int]
    score_penalty_home: Optional[int]
    score_penalty_away: Optional[int]
    odds: Optional[FixtureOddsSchema]
    prediction: Optional[PredictionBase]

    model_config = ConfigDict(from_attributes=True)


class PredictionSchema(BaseModel):
    id: int
    fixture_id: int
    winner_team_id: Optional[int]
    win_or_draw: Optional[bool]
    under_over: Optional[str]
    goals_home: Optional[str]
    goals_away: Optional[str]
    advice: Optional[str]
    percent_home: Optional[str]
    percent_draw: Optional[str]
    percent_away: Optional[str]
    comparison: Optional[Dict[str, Any]]

    model_config = ConfigDict(from_attributes=True)




class TeamStanding(BaseModel):
    rank: int
    team: TeamBase
    matches_played: int
    points: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_difference: int

    model_config = ConfigDict(from_attributes=True)




class TeamStatistics(BaseModel):
    team: TeamBase
    matches_played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_difference: int
    average_possession: Optional[float] = None
    clean_sheets: int
    average_shots_on_target: Optional[float] = None
    average_tackles: Optional[float] = None
    average_key_passes: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)




class PlayerRanking(BaseModel):
    rank: int
    player: PlayerBase
    stat_value: int

    model_config = ConfigDict(from_attributes=True)



class PredictionAccuracy(BaseModel):
    total_predictions: int
    correct_predictions: int
    accuracy: float

    model_config = ConfigDict(from_attributes=True)


FixtureBaseDetailed.model_rebuild()


class FixtureH2HStats(BaseModel):
    total_matches: int
    home_team_wins: int
    away_team_wins: int
    draws: int
    recent_matches: List[Dict[str, Any]]

class TeamRecentForm(BaseModel):
    fixture_id: int
    date: datetime
    opponent: str
    opponent_logo: Optional[str] = None
    opponent_team_id: int
    home_or_away: str
    goals_for: int
    goals_against: int
    outcome: str  # 'W', 'D', 'L'

    model_config = ConfigDict(from_attributes=True)

class TeamStatistics(BaseModel):
    matches_played: int
    wins: int
    draws: int
    losses: int
    goals_for: int
    goals_against: int
    goal_difference: int
    clean_sheets: int
    average_shots_on_target: Optional[float]
    average_tackles: Optional[float]
    average_passes_accuracy: Optional[float]

    model_config = ConfigDict(from_attributes=True)

class TopPlayer(BaseModel):
    player_id: int
    name: str
    position: str
    goals: Optional[int]
    photo: Optional[str]

class FixtureDetailedResponse(FixtureBaseDetailed):
    h2h_stats: Optional[FixtureH2HStats] = None
    home_recent_form: Optional[List[TeamRecentForm]] = None
    away_recent_form: Optional[List[TeamRecentForm]] = None
    home_team_stats: Optional[TeamStatistics] = None
    away_team_stats: Optional[TeamStatistics] = None
    home_top_players: Optional[List[TopPlayer]] = None
    away_top_players: Optional[List[TopPlayer]] = None
    match_statistics: Optional[Dict[str, Dict[str, Any]]] = None  # Updated line
    match_events: Optional[List[MatchEvent]] = None

    model_config = ConfigDict(from_attributes=True)


class MatchStatistics(BaseModel):
    fixture_id: int
    team_id: int
    statistics: List[Dict[str, Any]]  # Assuming statistics is a list of dicts

    model_config = ConfigDict(from_attributes=True)

class MatchEvent(BaseModel):
    fixture_id: int
    minute: int
    team_id: int
    player_id: Optional[int]
    player_name: Optional[str]
    type: str
    detail: Optional[str]
    comments: Optional[str]



FixtureBase.model_rebuild()
FixtureDetailedResponse.model_rebuild()