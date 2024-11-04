from __future__ import annotations
from pydantic import BaseModel
from typing import Dict, Optional, Any, List
from datetime import date, datetime

class BookmakerSchema(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class BetTypeSchema(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True

class OddValueSchema(BaseModel):
    id: int
    value: str
    odd: str

    class Config:
        from_attributes = True

class BetSchema(BaseModel):
    id: int
    bet_type: BetTypeSchema
    odd_values: List[OddValueSchema]

    class Config:
        from_attributes = True

class FixtureBookmakerSchema(BaseModel):
    id: int
    bookmaker: BookmakerSchema
    bets: List[BetSchema]

    class Config:
        from_attributes = True

class FixtureOddsSchema(BaseModel):
    id: int
    update_time: datetime
    fixture_id: int
    fixture_bookmakers: List[FixtureBookmakerSchema]

    class Config:
        from_attributes = True

class LeagueBase(BaseModel):
    league_id: int
    name: str
    type: Optional[str]
    logo: Optional[str]
    country_name: Optional[str]
    country_code: Optional[str]
    country_flag: Optional[str]

    class Config:
        from_attributes = True

class SeasonBase(BaseModel):
    id: int
    league_id: int
    year: int
    start: Optional[date]
    end: Optional[date]
    current: bool
    coverage: Optional[Any] = None

    class Config:
        from_attributes = True

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

    class Config:
        from_attributes = True

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

    class Config:
        from_attributes = True

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

    class Config:
        from_attributes = True

class VenueBase(BaseModel):
    id: Optional[int] = None
    name: Optional[str]
    city: Optional[str]

    class Config:
        from_attributes = True

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

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True

class LeagueWithTeams(LeagueBase):
    teams: List[TeamBase] = []

    class Config:
        from_attributes = True



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

    class Config:
        from_attributes = True

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

    class Config:
        from_attributes = True