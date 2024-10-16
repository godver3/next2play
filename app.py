from flask import Flask, request, render_template, jsonify
import json
import random
import subprocess
import logging
from howlongtobeatpy import HowLongToBeat

app = Flask(__name__)

def load_games():
    with open('games_data.json', 'r') as f:
        return json.load(f)

def save_games(games):
    with open('games_data.json', 'w') as f:
        json.dump(games, f, indent=2)

@app.route('/')
def index():
    sort_column = request.args.get('sort_column', 'GameName')
    sort_order = request.args.get('sort_order', 'ASC')

    games = load_games()

    def custom_sort(game):
        if game['ProgressStatus'] == 'In Progress':
            return (0, game['GameName'].lower())
        return (1, game['GameName'].lower())

    games.sort(key=custom_sort)

    if sort_order == 'DESC':
        games.reverse()

    # Check if this is an AJAX request
    if request.args.get('ajax'):
        return jsonify(games)

    return render_template('index.html', games=games, sort_column=sort_column, sort_order=sort_order)

@app.route('/add_game', methods=['POST'])
def add_game():
    data = request.form
    game_name = data['GameName']

    try:
        results = HowLongToBeat().search(game_name)
        
        if results:
            game_info = results[0]
            logging.info(f"Game info: {vars(game_info)}")
            
            game_id = game_info.game_id
            image_url = game_info.game_image_url if hasattr(game_info, 'game_image_url') else ''
            how_long_to_beat = game_info.main_story  # Use main_story instead of gameplay_main

            games = load_games()

            existing_game = next((game for game in games if game['GameID'] == game_id), None)

            if existing_game:
                return 'Duplicate game found', 409
            else:
                new_game = {
                    "GameID": game_id,
                    "GameName": game_name,
                    "HowLongToBeat": "Unreleased" if how_long_to_beat == 0 else round(how_long_to_beat),
                    "ProgressStatus": "Not Started",
                    "ImageURL": image_url
                }
                games.append(new_game)
                save_games(games)
                return 'Game added successfully', 200
        else:
            return 'Game not found', 404
    except Exception as e:
        logging.error(f"Unexpected error in add_game: {e}")
        return f'Unexpected error: {e}', 500

@app.route('/update_games', methods=['POST'])
def update_games():
    games = load_games()
    updated_count = 0
    for game in games:
        if game['HowLongToBeat'] == '0' or game['HowLongToBeat'] == 0 or game['HowLongToBeat'] == 'Unreleased':
            result = subprocess.run(['node', 'hltbSearch.js', game['GameName']], capture_output=True, text=True)
            if result.stdout:
                search_results = json.loads(result.stdout)
                if search_results:
                    game_info = search_results[0]
                    new_how_long_to_beat = "Unreleased" if game_info['gameplayMain'] == 0 else game_info['gameplayMain']
                    new_image_url = game_info.get('imageUrl', '')

                    # Check if anything has actually changed
                    if (new_how_long_to_beat != game['HowLongToBeat'] or
                        new_image_url != game.get('ImageURL', '') or
                        not isinstance(game['GameID'], int)):  # Check if GameID is not an integer
                        game['HowLongToBeat'] = new_how_long_to_beat
                        game['ImageURL'] = new_image_url
                        game['GameID'] = int(game_info['id'])  # Ensure GameID is an integer
                        updated_count += 1

    save_games(games)

    if updated_count > 0:
        return jsonify({"message": f"Updated {updated_count} games"}), 200
    else:
        return jsonify({"message": "No games needed updating"}), 200

@app.route('/delete_game/<game_id>', methods=['DELETE'])
def delete_game(game_id):
    games = load_games()
    initial_count = len(games)
    
    # Convert game_id to int if it's a numeric string
    try:
        game_id = int(game_id)
    except ValueError:
        pass  # Keep it as a string if it's not a valid integer

    games = [game for game in games if str(game['GameID']) != str(game_id)]
    
    if len(games) < initial_count:
        save_games(games)
        return jsonify({"message": "Game deleted successfully", "success": True}), 200
    else:
        return jsonify({"message": "Game not found", "success": False}), 404

@app.route('/update_status/<int:game_id>', methods=['POST'])
def update_status(game_id):
    data = request.json
    new_status = data.get('status')

    games = load_games()
    for game in games:
        if game['GameID'] == game_id:
            game['ProgressStatus'] = new_status
            break
    save_games(games)

    return jsonify({"message": "Status updated successfully"}), 200


@app.route('/random_game')
def random_game():
    games = load_games()
    not_started_games = [game['GameName'] for game in games if game['ProgressStatus'] == 'Not Started']

    if not_started_games:
        game_name = random.choice(not_started_games)
    else:
        game_name = "No 'Not Started' games available"

    return jsonify({"gameName": game_name}), 200

@app.route('/in_progress_game')
def in_progress_game():
    games = load_games()
    in_progress = next((game for game in games if game['ProgressStatus'] == 'In Progress'), None)
    return jsonify({"game": in_progress})

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5015)
