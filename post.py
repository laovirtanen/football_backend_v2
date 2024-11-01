import requests

response = requests.post("http://127.0.0.1:8000/player_statistics/")
print(response.json())
