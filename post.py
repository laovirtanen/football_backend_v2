import requests

# Base URL of your FastAPI application
BASE_URL = "http://127.0.0.1:8000"

# Step 1: Ingest leagues
response = requests.post(f"{BASE_URL}/leagues/")
if response.ok:
    leagues_data = response.json()
    print(f"Leagues ingestion response: {response.status_code}, {leagues_data}")
else:
    print(f"Leagues ingestion failed with status code: {response.status_code}, response text: {response.text}")

# Step 2: Ingest teams
response = requests.post(f"{BASE_URL}/teams/")
if response.ok:
    teams_data = response.json()
    print(f"Teams ingestion response: {response.status_code}, {teams_data}")
else:
    print(f"Teams ingestion failed with status code: {response.status_code}, response text: {response.text}")

# Step 3: Ingest players
response = requests.post(f"{BASE_URL}/players/")
if response.ok:
    players_data = response.json()
    print(f"Players ingestion response: {response.status_code}, {players_data}")
else:
    print(f"Players ingestion failed with status code: {response.status_code}, response text: {response.text}")

# Step 4: Ingest player statistics
response = requests.post(f"{BASE_URL}/player_statistics/")
if response.ok:
    player_statistics_data = response.json()
    print(f"Player Statistics ingestion response: {response.status_code}, {player_statistics_data}")
else:
    print(f"Player Statistics ingestion failed with status code: {response.status_code}, response text: {response.text}")

# Step 5: Ingest fixtures
response = requests.post(f"{BASE_URL}/fixtures/")
if response.ok:
    fixtures_data = response.json()
    print(f"Fixtures ingestion response: {response.status_code}, {fixtures_data}")
else:
    print(f"Fixtures ingestion failed with status code: {response.status_code}, response text: {response.text}")

# Step 6: Ingest fixtures data (odds and predictions together)
response = requests.post(f"{BASE_URL}/ingest/fixtures_data/")
if response.ok:
    fixtures_data = response.json()
    print(f"Fixtures data ingestion response: {response.status_code}, {fixtures_data}")
else:
    print(f"Fixtures data ingestion failed with status code: {response.status_code}, response text: {response.text}")
