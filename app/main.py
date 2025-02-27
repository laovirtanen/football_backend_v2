# app/main.py

from fastapi import FastAPI
from .database import engine, Base
from fastapi.middleware.cors import CORSMiddleware
from .routers.ingestion import ingest_leagues, ingest_teams, ingest_players, ingest_player_statistics, ingest_fixtures, ingest_odds, ingest_predictions, ingest_fixtures_data
from .routers.retrieval import (
    leagues,
    teams,
    fixtures,
    bookmakers,
    odds,
    predictions,
    players,
    standings,
    head_to_head,
    player_statistics
)
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup code: create tables
    # async with engine.begin() as conn:
    #     await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown code: dispose engine
    await engine.dispose()


app = FastAPI(lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(ingest_leagues.router)
app.include_router(ingest_teams.router)
app.include_router(ingest_players.router)
app.include_router(ingest_player_statistics.router)
app.include_router(ingest_fixtures.router)
app.include_router(ingest_odds.router)
app.include_router(ingest_predictions.router)
app.include_router(ingest_fixtures_data.router)



# Include retrieval routers
app.include_router(leagues.router)
app.include_router(teams.router)
app.include_router(fixtures.router)
app.include_router(bookmakers.router)
app.include_router(odds.router)
app.include_router(predictions.router)
app.include_router(players.router)
app.include_router(standings.router)
app.include_router(head_to_head.router)
app.include_router(player_statistics.router)
