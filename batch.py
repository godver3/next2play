import csv
import requests

# URL of the Flask add_game endpoint
url = 'http://localhost:5000/add_game'

# Path to the CSV file
csv_file_path = '/root/next2play/games.csv'

# Read the CSV file and send POST requests to the add_game endpoint
with open(csv_file_path, mode='r') as file:
    csv_reader = csv.reader(file)
    next(csv_reader)  # Skip the header row
    for row in csv_reader:
        game_title = row[0]
        data = {'GameName': game_title}
        response = requests.post(url, data=data)
        if response.status_code == 204:
            print(f"Successfully added {game_title}")
        else:
            print(f"Failed to add {game_title}: {response.text}")
