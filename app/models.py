# app/models.py

from sqlalchemy import Column, DateTime, Integer, String, ForeignKey, Boolean, Date, JSON, Float
from sqlalchemy.orm import relationship
from app.database import Base

class League(Base):
    __tablename__ = "leagues"

    league_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    type = Column(String)
    logo = Column(String)
    country_name = Column(String)
    country_code = Column(String, nullable=True)
    country_flag = Column(String, nullable=True)

    seasons = relationship("Season", back_populates="league", cascade="all, delete-orphan")
    teams = relationship("Team", back_populates="league", cascade="all, delete-orphan")
    fixtures = relationship("Fixture", back_populates="league", cascade="all, delete-orphan")



class Season(Base):
    __tablename__ = "seasons"

    id = Column(Integer, primary_key=True, index=True)
    league_id = Column(Integer, ForeignKey("leagues.league_id"), index=True)
    year = Column(Integer)
    start = Column(Date)
    end = Column(Date)
    current = Column(Boolean)
    coverage = Column(JSON)

    league = relationship("League", back_populates="seasons")

class Team(Base):
    __tablename__ = "teams"

    team_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    code = Column(String, nullable=True)
    country = Column(String, nullable=True)
    founded = Column(Integer, nullable=True)
    national = Column(Boolean)
    logo = Column(String, nullable=True)
    league_id = Column(Integer, ForeignKey("leagues.league_id"), nullable=False)
    season_year = Column(Integer, nullable=False)  # New column

    league = relationship("League", back_populates="teams")
    players = relationship("Player", back_populates="team", cascade="all, delete-orphan")

class Player(Base):
    __tablename__ = "players"

    player_id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    firstname = Column(String, nullable=True)
    lastname = Column(String, nullable=True)
    age = Column(Integer, nullable=True)
    birth_date = Column(Date, nullable=True)
    birth_place = Column(String, nullable=True)
    birth_country = Column(String, nullable=True)
    nationality = Column(String, nullable=True)
    height = Column(String, nullable=True)
    weight = Column(String, nullable=True)
    injured = Column(Boolean, nullable=True)
    photo = Column(String, nullable=True)
    team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)
    season_year = Column(Integer, nullable=False)  # New column

    team = relationship("Team", back_populates="players")
    statistics = relationship("PlayerStatistics", back_populates="player", cascade="all, delete-orphan")




class PlayerStatistics(Base):
    __tablename__ = "player_statistics"

    id = Column(Integer, primary_key=True, index=True)
    player_id = Column(Integer, ForeignKey("players.player_id"), nullable=False)
    team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)
    league_id = Column(Integer, ForeignKey("leagues.league_id"), nullable=False)
    season_year = Column(Integer, nullable=False)

    # Game statistics
    appearances = Column(Integer, nullable=True)
    lineups = Column(Integer, nullable=True)
    minutes = Column(Integer, nullable=True)
    number = Column(Integer, nullable=True)
    position = Column(String, nullable=True)
    rating = Column(Float, nullable=True)
    captain = Column(Boolean, nullable=True)

    # Substitute statistics
    subs_in = Column(Integer, nullable=True)
    subs_out = Column(Integer, nullable=True)
    subs_bench = Column(Integer, nullable=True)

    # Shots statistics
    shots_total = Column(Integer, nullable=True)
    shots_on = Column(Integer, nullable=True)

    # Goals statistics
    goals_total = Column(Integer, nullable=True)
    goals_conceded = Column(Integer, nullable=True)
    goals_assists = Column(Integer, nullable=True)
    goals_saves = Column(Integer, nullable=True)

    # Passes statistics
    passes_total = Column(Integer, nullable=True)
    passes_key = Column(Integer, nullable=True)
    passes_accuracy = Column(Integer, nullable=True)

    # Tackles statistics
    tackles_total = Column(Integer, nullable=True)
    tackles_blocks = Column(Integer, nullable=True)
    tackles_interceptions = Column(Integer, nullable=True)

    # Duels statistics
    duels_total = Column(Integer, nullable=True)
    duels_won = Column(Integer, nullable=True)

    # Dribbles statistics
    dribbles_attempts = Column(Integer, nullable=True)
    dribbles_success = Column(Integer, nullable=True)
    dribbles_past = Column(Integer, nullable=True)

    # Fouls statistics
    fouls_drawn = Column(Integer, nullable=True)
    fouls_committed = Column(Integer, nullable=True)

    # Cards statistics
    cards_yellow = Column(Integer, nullable=True)
    cards_yellowred = Column(Integer, nullable=True)
    cards_red = Column(Integer, nullable=True)

    # Penalty statistics
    penalty_won = Column(Integer, nullable=True)
    penalty_committed = Column(Integer, nullable=True)
    penalty_scored = Column(Integer, nullable=True)
    penalty_missed = Column(Integer, nullable=True)
    penalty_saved = Column(Integer, nullable=True)

    # Relationships
    player = relationship("Player", back_populates="statistics")
    team = relationship("Team")
    league = relationship("League")


class Venue(Base):
    __tablename__ = "venues"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=True)
    city = Column(String, nullable=True)

    fixtures = relationship("Fixture", back_populates="venue")

class Fixture(Base):
    __tablename__ = "fixtures"

    fixture_id = Column(Integer, primary_key=True, index=True)
    referee = Column(String, nullable=True)
    timezone = Column(String, nullable=False)
    date = Column(DateTime(timezone=True), nullable=True)
    timestamp = Column(Integer, nullable=False)
    venue_id = Column(Integer, ForeignKey("venues.id"), nullable=True)
    status_long = Column(String, nullable=False)
    status_short = Column(String, nullable=False)
    status_elapsed = Column(Integer, nullable=True)
    status_extra = Column(String, nullable=True)
    is_final = Column(Boolean, default=False)

    league_id = Column(Integer, ForeignKey("leagues.league_id"), nullable=False)

    season_year = Column(Integer, nullable=False)
    round = Column(String, nullable=True)

    home_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)
    away_team_id = Column(Integer, ForeignKey("teams.team_id"), nullable=False)


    goals_home = Column(Integer, nullable=True)
    goals_away = Column(Integer, nullable=True)

    score_halftime_home = Column(Integer, nullable=True)
    score_halftime_away = Column(Integer, nullable=True)
    score_fulltime_home = Column(Integer, nullable=True)
    score_fulltime_away = Column(Integer, nullable=True)
    score_extratime_home = Column(Integer, nullable=True)
    score_extratime_away = Column(Integer, nullable=True)
    score_penalty_home = Column(Integer, nullable=True)
    score_penalty_away = Column(Integer, nullable=True)

    home_team = relationship("Team", foreign_keys=[home_team_id])
    away_team = relationship("Team", foreign_keys=[away_team_id])
    league = relationship("League", back_populates="fixtures")
    venue = relationship("Venue", back_populates="fixtures")
    odds = relationship("FixtureOdds", back_populates="fixture", uselist=False)
    prediction = relationship("Prediction", uselist=False, back_populates="fixture")

class Bookmaker(Base):
    __tablename__ = "bookmakers"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)

    fixture_bookmakers = relationship("FixtureBookmaker", back_populates="bookmaker")


class BetType(Base):
    __tablename__ = "bet_types"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)

    bets = relationship("Bet", back_populates="bet_type")


class FixtureOdds(Base):
    __tablename__ = "fixture_odds"

    id = Column(Integer, primary_key=True)
    fixture_id = Column(Integer, ForeignKey("fixtures.fixture_id"), nullable=False)
    update_time = Column(DateTime(timezone=True), nullable=False)

    fixture = relationship("Fixture", back_populates="odds")
    fixture_bookmakers = relationship("FixtureBookmaker", back_populates="fixture_odds")


class FixtureBookmaker(Base):
    __tablename__ = "fixture_bookmakers"

    id = Column(Integer, primary_key=True)
    fixture_odds_id = Column(Integer, ForeignKey("fixture_odds.id"), nullable=False)
    bookmaker_id = Column(Integer, ForeignKey("bookmakers.id"), nullable=False)

    fixture_odds = relationship("FixtureOdds", back_populates="fixture_bookmakers")
    bookmaker = relationship("Bookmaker", back_populates="fixture_bookmakers")
    bets = relationship("Bet", back_populates="fixture_bookmaker")


class Bet(Base):
    __tablename__ = "bets"

    id = Column(Integer, primary_key=True)
    fixture_bookmaker_id = Column(Integer, ForeignKey("fixture_bookmakers.id"), nullable=False)
    bet_type_id = Column(Integer, ForeignKey("bet_types.id"), nullable=False)

    fixture_bookmaker = relationship("FixtureBookmaker", back_populates="bets")
    bet_type = relationship("BetType", back_populates="bets")
    odd_values = relationship("OddValue", back_populates="bet")


class OddValue(Base):
    __tablename__ = "odd_values"

    id = Column(Integer, primary_key=True)
    bet_id = Column(Integer, ForeignKey("bets.id"), nullable=False)
    value = Column(String, nullable=False)
    odd = Column(String, nullable=False)

    bet = relationship("Bet", back_populates="odd_values")


class Prediction(Base):
    __tablename__ = "predictions"
    id = Column(Integer, primary_key=True, index=True)
    fixture_id = Column(Integer, ForeignKey("fixtures.fixture_id"), unique=True)
    winner_team_id = Column(Integer, ForeignKey("teams.team_id"))
    win_or_draw = Column(Boolean)
    under_over = Column(String)
    goals_home = Column(String)
    goals_away = Column(String)
    advice = Column(String)
    percent_home = Column(String)
    percent_draw = Column(String)
    percent_away = Column(String)
    comparison = Column(JSON)

    fixture = relationship("Fixture", back_populates="prediction")
    winner_team = relationship("Team")