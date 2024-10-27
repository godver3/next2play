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
    search_term = data['GameName']
    submitted_id = int(data['GameID'])
    submitted_year = int(data['ReleaseYear']) if data['ReleaseYear'] else None
    submitted_hltb = float(data['HowLongToBeat']) if data['HowLongToBeat'] else 0

    try:
        results = HowLongToBeat().search(search_term)
        
        if results:
            # Find the specific game version that was selected
            game_info = next((game for game in results if game.game_id == submitted_id), None)
            
            if game_info:
                game_id = game_info.game_id
                game_name = game_info.game_name
                image_url = game_info.game_image_url if hasattr(game_info, 'game_image_url') else ''
                how_long_to_beat = "Unreleased" if submitted_hltb == 0 else round(submitted_hltb)
                release_year = submitted_year

                games = load_games()

                # Check for duplicate based on exact match of name, year, and length
                existing_game = next(
                    (game for game in games 
                     if game['GameName'] == game_name 
                     and game['ReleaseYear'] == release_year 
                     and str(game['HowLongToBeat']) == str(how_long_to_beat)), 
                    None
                )

                if existing_game:
                    return 'Duplicate game found', 409
                else:
                    new_game = {
                        "GameID": game_id,
                        "GameName": game_name,
                        "HowLongToBeat": how_long_to_beat,
                        "ProgressStatus": "Not Started",
                        "ImageURL": image_url,
                        "ReleaseYear": release_year
                    }
                    games.append(new_game)
                    save_games(games)
                    return 'Game added successfully', 200
            else:
                return 'Selected game version not found', 404
        else:
            return 'Game not found', 404
    except Exception as e:
        logging.error(f"Unexpected error in add_game: {e}")
        return f'Unexpected error: {e}', 500

@app.route('/update_games', methods=['POST'])
def update_games():
    try:
        games = load_games()
        updated_count = 0
        
        for game in games:
            # Check if game needs updating
            needs_update = (
                game['HowLongToBeat'] == "Unreleased" or
                'ReleaseYear' not in game or 
                not game['ReleaseYear'] or
                'ImageURL' not in game or
                not game['ImageURL']
            )
            
            if needs_update:
                results = HowLongToBeat().search(game['GameName'])
                if results:
                    # Find the matching game by ID
                    game_info = next((result for result in results 
                                    if result.game_id == game['GameID']), results[0])
                    
                    # Update HowLongToBeat if it was "Unreleased"
                    if game['HowLongToBeat'] == "Unreleased" and game_info.main_story > 0:
                        game['HowLongToBeat'] = round(game_info.main_story)
                        updated_count += 1
                    
                    # Update or add release year if missing
                    if ('ReleaseYear' not in game or not game['ReleaseYear']) and hasattr(game_info, 'release_world'):
                        game['ReleaseYear'] = game_info.release_world
                        updated_count += 1
                    
                    # Update or add image URL if missing
                    if ('ImageURL' not in game or not game['ImageURL']) and hasattr(game_info, 'game_image_url'):
                        game['ImageURL'] = game_info.game_image_url
                        updated_count += 1

        if updated_count > 0:
            save_games(games)
        
        message = f"Updated {updated_count} fields" if updated_count > 0 else "No updates needed"
        return jsonify({"message": message, "success": True})
    except Exception as e:
        logging.error(f"Error updating games: {e}")
        return jsonify({"message": f"Error updating games: {str(e)}", "success": False})

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

@app.route('/search_games', methods=['POST'])
def search_games():
    data = request.json
    search_term = data['GameName']
    
    try:
        results = HowLongToBeat().search(search_term)
        if results:
            games_data = [{
                'game_id': game.game_id,
                'game_name': game.game_name,
                'game_image_url': game.game_image_url if hasattr(game, 'game_image_url') else '',
                'release_world': game.release_world if hasattr(game, 'release_world') else None,
                'main_story': game.main_story
            } for game in results]
            return jsonify(games_data)
        return jsonify([])
    except Exception as e:
        logging.error(f"Error searching games: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5015)
