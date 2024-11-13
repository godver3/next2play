from flask import Flask, request, render_template, jsonify
import json
import random
import subprocess
import logging
import requests
from bs4 import BeautifulSoup
import time
from howlongtobeatpy import HowLongToBeat
import re

app = Flask(__name__)

# Set up more detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def load_games():
    with open('games_data.json', 'r') as f:
        return json.load(f)

def save_games(games):
    with open('games_data.json', 'w') as f:
        json.dump(games, f, indent=2)

def search_hltb(search_term):
    url = "https://howlongtobeat.com/api/search"
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    payload = {
        "searchType": "games",
        "searchTerms": [search_term],
        "searchPage": 1,
        "size": 20,
        "searchOptions": {
            "games": {
                "userId": 0,
                "platform": "",
                "sortCategory": "popular",
                "rangeCategory": "main",
                "rangeTime": {
                    "min": 0,
                    "max": 0
                },
                "gameplay": {
                    "perspective": "",
                    "flow": "",
                    "genre": ""
                },
                "modifier": ""
            },
            "users": {
                "sortCategory": "postcount"
            },
            "filter": "",
            "sort": 0,
            "randomizer": 0
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        if 'data' in data:
            return [{
                'game_id': game.get('game_id'),
                'game_name': game.get('game_name', 'Unknown'),
                'game_image_url': f"https://howlongtobeat.com/games/{game.get('game_image', '')}" if game.get('game_image') else '',
                'release_world': game.get('release_world'),
                'main_story': game.get('comp_main', 0)
            } for game in data['data']]
        return []
    except Exception as e:
        logging.error(f"Error in search_hltb: {str(e)}")
        return []

def get_hltb_user_id():
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }
        
        # Get main page
        logger.debug("Fetching main page...")
        response = requests.get("https://howlongtobeat.com/", headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        
        # Find app.js path
        app_src = None
        for line in soup.prettify().split("\n"):
            if "_app-" in line and "chunks/pages/" in line:
                app_src = re.search(r'src="([^"]*)"', line).group(1)
                break
        
        if not app_src:
            raise ValueError("Could not find app.js path")
            
        # Get app.js content
        logger.debug(f"Fetching app.js from {app_src}...")
        app_url = f"https://howlongtobeat.com{app_src}"
        response = requests.get(app_url, headers=headers)
        response.raise_for_status()
        
        # Extract user ID
        for line in response.content.decode().split("\n"):
            match = re.search(r'users:\{id:"([^"]+)"', line)
            if match:
                user_id = match.group(1)
                logger.debug(f"Found user ID: {user_id}")
                return user_id
                
        raise ValueError("Could not find user ID in app.js")
        
    except Exception as e:
        logger.error(f"Error getting HLTB user ID: {str(e)}")
        return None

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
        # Get user ID for API request
        user_id = get_hltb_user_id()
        if not user_id:
            raise ValueError("Failed to get HLTB user ID")
            
        # Search for the game using our direct API call
        url = "https://howlongtobeat.com/api/search"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Content-Type": "application/json",
            "Origin": "https://howlongtobeat.com",
            "Referer": "https://howlongtobeat.com/"
        }
        
        payload = {
            "searchType": "games",
            "searchTerms": [search_term],
            "searchPage": 1,
            "size": 20,
            "searchOptions": {
                "games": {
                    "userId": 0,
                    "platform": "",
                    "sortCategory": "popular",
                    "rangeCategory": "main",
                    "rangeTime": {"min": None, "max": None},
                    "gameplay": {"perspective": "", "flow": "", "genre": ""},
                    "rangeYear": {"min": "", "max": ""},
                    "modifier": ""
                },
                "users": {
                    "id": user_id,
                    "sortCategory": "postcount"
                },
                "lists": {"sortCategory": "follows"},
                "filter": "",
                "sort": 0,
                "randomizer": 0
            },
            "useCache": True
        }
        
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        results = response.json().get('data', [])
        
        if results:
            # Find the specific game version that was selected
            game_info = next((game for game in results if game['game_id'] == submitted_id), None)
            
            if game_info:
                game_id = game_info['game_id']
                game_name = game_info['game_name']
                image_url = f"https://howlongtobeat.com/games/{game_info['game_image']}" if game_info.get('game_image') else ''
                # Convert minutes to hours for the submitted time or use "Unreleased"
                how_long_to_beat = "Unreleased" if submitted_hltb == 0 else round(submitted_hltb / 60)
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
        logging.error(f"Unexpected error in add_game: {str(e)}")
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
    try:
        data = request.json
        search_term = data['GameName']
        
        logger.debug(f"Initializing direct search for term: {search_term}")
        
        # Get user ID
        user_id = get_hltb_user_id()
        if not user_id:
            raise ValueError("Failed to get HLTB user ID")
        
        url = "https://howlongtobeat.com/api/search"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://howlongtobeat.com/",
            "Content-Type": "application/json",
            "Origin": "https://howlongtobeat.com",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "TE": "trailers"
        }
        
        payload = {
            "searchType": "games",
            "searchTerms": [search_term],
            "searchPage": 1,
            "size": 20,
            "searchOptions": {
                "games": {
                    "userId": 0,
                    "platform": "",
                    "sortCategory": "popular",
                    "rangeCategory": "main",
                    "rangeTime": {"min": None, "max": None},
                    "gameplay": {"perspective": "", "flow": "", "genre": ""},
                    "rangeYear": {"min": "", "max": ""},
                    "modifier": ""
                },
                "users": {
                    "id": user_id,
                    "sortCategory": "postcount"
                },
                "lists": {"sortCategory": "follows"},
                "filter": "",
                "sort": 0,
                "randomizer": 0
            },
            "useCache": True
        }
        
        logger.debug("Sending request to HLTB API")
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        
        data = response.json()
        logger.debug(f"Received response: {data}")
        
        if 'data' in data:
            games_data = []
            for game in data['data']:
                # Convert minutes to hours and round to nearest hour
                main_story_hours = round(game.get('comp_main', 0) / 60) if game.get('comp_main') else 0
                
                game_data = {
                    'game_id': game.get('game_id'),
                    'game_name': game.get('game_name', 'Unknown'),
                    'game_image_url': f"https://howlongtobeat.com/games/{game.get('game_image', '')}" if game.get('game_image') else '',
                    'release_world': game.get('release_world'),
                    'main_story': main_story_hours
                }
                if game_data['game_id'] is not None:
                    games_data.append(game_data)
            
            logger.debug(f"Processed {len(games_data)} games")
            return jsonify(games_data)
            
        logger.debug("No results found")
        return jsonify([])
        
    except Exception as e:
        logger.error(f"Error searching games: {str(e)}")
        logger.exception("Full traceback:")
        return jsonify({
            'error': 'An error occurred while searching for games',
            'details': str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5015)
