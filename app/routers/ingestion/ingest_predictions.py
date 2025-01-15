# app/routers/ingestion/predictions.py

import logging
import os
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import httpx

from app.database import get_db
from app import models

router = APIRouter(
    prefix="/predictions",
    tags=["predictions"]
)

API_FOOTBALL_KEY = os.getenv("API_FOOTBALL_KEY")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@router.post("/", response_model=dict)
async def fetch_and_store_predictions(db: AsyncSession = Depends(get_db)):
    logger.info("Starting the predictions ingestion process.")
    try:
        # Validate API key
        if not API_FOOTBALL_KEY:
            logger.error("API_FOOTBALL_KEY environment variable is not set.")
            raise HTTPException(status_code=500, detail="API key not configured.")

        headers = {
            'x-apisports-key': API_FOOTBALL_KEY,
            'Accept': 'application/json'
        }

        async with httpx.AsyncClient() as client:
            # Fetch all fixtures 
            fixtures_result = await db.execute(
                select(models.Fixture.fixture_id)
            )
            fixture_ids = [fixture_id for (fixture_id,) in fixtures_result.fetchall()]

            if not fixture_ids:
                logger.info("No fixtures found.")
                return {"message": "No fixtures found."}

            predictions_processed = 0

            for fixture_id in fixture_ids:
                logger.info(f"Fetching prediction for fixture ID: {fixture_id}")

                params = {
                    'fixture': fixture_id
                }

                response = await client.get(
                    "https://v3.football.api-sports.io/predictions",
                    headers=headers,
                    params=params
                )

                if response.status_code != 200:
                    logger.error(f"Failed to fetch prediction for fixture {fixture_id}: {response.text}")
                    continue

                data = response.json()
                predictions_response = data.get("response", [])

                if not predictions_response:
                    logger.info(f"No prediction available for fixture {fixture_id}.")
                    continue

                prediction_data = predictions_response[0]

                # Extract prediction details
                predictions = prediction_data.get("predictions", {})
                winner = predictions.get("winner", {})
                win_or_draw = predictions.get("win_or_draw")
                under_over = predictions.get("under_over")
                goals = predictions.get("goals", {})
                advice = predictions.get("advice")
                percent = predictions.get("percent", {})
                comparison = prediction_data.get("comparison", {})

                # Check if prediction already exists
                existing_prediction = await db.get(models.Prediction, fixture_id)

                if existing_prediction:
                    # Update existing prediction
                    existing_prediction.winner_team_id = winner.get("id")
                    existing_prediction.win_or_draw = win_or_draw
                    existing_prediction.under_over = under_over
                    existing_prediction.goals_home = goals.get("home")
                    existing_prediction.goals_away = goals.get("away")
                    existing_prediction.advice = advice
                    existing_prediction.percent_home = percent.get("home")
                    existing_prediction.percent_draw = percent.get("draw")
                    existing_prediction.percent_away = percent.get("away")
                    existing_prediction.comparison = comparison
                else:
                    # Store new prediction
                    prediction = models.Prediction(
                        fixture_id=fixture_id,
                        winner_team_id=winner.get("id"),
                        win_or_draw=win_or_draw,
                        under_over=under_over,
                        goals_home=goals.get("home"),
                        goals_away=goals.get("away"),
                        advice=advice,
                        percent_home=percent.get("home"),
                        percent_draw=percent.get("draw"),
                        percent_away=percent.get("away"),
                        comparison=comparison
                    )
                    db.add(prediction)

                await db.commit()
                predictions_processed += 1

            logger.info(f"Finished fetching and storing predictions. Total predictions processed: {predictions_processed}")
            return {"message": "Predictions fetched and stored successfully", "processed": predictions_processed}

    except Exception as e:
        logger.error(f"An error occurred during predictions ingestion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
