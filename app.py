from flask import Flask, request, render_template, jsonify
import json
import random
import subprocess
import logging
import requests
from bs4 import BeautifulSoup
import time
from howlongtobeatpy import HowLongToBeat
import os
import requests
from urllib.parse import urlparse

app = Flask(__name__)

# Set up more detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def load_games():
    with open('games_data.json', 'r') as f:
        games = json.load(f)
        # Format display times while keeping original data
        for game in games:
            if game['HowLongToBeat'] != "Unreleased":
                try:
                    # Store original time in a new field if needed
                    game['HowLongToBeatRaw'] = game['HowLongToBeat']
                    # Round for display
                    game['HowLongToBeat'] = str(round(float(game['HowLongToBeat'])))
                except (ValueError, TypeError):
                    # Keep original value if conversion fails
                    pass
        return games

def save_games(games):
    with open('games_data.json', 'w') as f:
        json.dump(games, f, indent=2)

def download_and_cache_image(image_url, game_id):
    """Download and cache an image locally"""
    if not image_url:
        return ''
    
    logging.info(f"Attempting to cache image for game {game_id} from {image_url}")
    
    # Create cache directory if it doesn't exist
    cache_dir = os.path.join('static', 'game_images')
    os.makedirs(cache_dir, exist_ok=True)
    
    # Get file extension from URL
    parsed_url = urlparse(image_url)
    ext = os.path.splitext(parsed_url.path)[1] or '.jpg'
    
    # Create local filename
    local_filename = f'game_{game_id}{ext}'
    local_path = os.path.join(cache_dir, local_filename)
    relative_path = f'/static/game_images/{local_filename}'
    
    logging.info(f"Local path will be: {local_path}")
    
    # If file doesn't exist, download it
    if not os.path.exists(local_path):
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'en-US,en;q=0.9',
                'Referer': 'https://howlongtobeat.com/'
            }
            response = requests.get(image_url, headers=headers)
            response.raise_for_status()
            with open(local_path, 'wb') as f:
                f.write(response.content)
        except Exception as e:
            logging.error(f"Error downloading image {image_url}: {e}")
            return image_url  # Return original URL if download fails
    
    # Return the local path relative to static directory
    return f'/static/game_images/{local_filename}'

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
                    # Cache the image locally
                    cached_image_url = download_and_cache_image(image_url, game_id)
                    logging.info(f"Original image URL: {image_url}")
                    logging.info(f"Cached image URL: {cached_image_url}")
                    
                    new_game = {
                        "GameID": game_id,
                        "GameName": game_name,
                        "HowLongToBeat": how_long_to_beat,
                        "ProgressStatus": "Not Started",
                        "ImageURL": cached_image_url,  # Make sure we're using the cached URL
                        "ReleaseYear": release_year
                    }
                    
                    # Before saving to JSON, log the game data
                    logging.info(f"Saving game with data: {new_game}")
                    
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
        cached_count = 0
        
        for game in games:
            # Check if we need to cache the image
            if game['ImageURL'] and game['ImageURL'].startswith('http'):
                logging.info(f"Caching image for {game['GameName']}")
                cached_url = download_and_cache_image(game['ImageURL'], game['GameID'])
                if cached_url and not cached_url.startswith('http'):
                    game['ImageURL'] = cached_url
                    cached_count += 1
            
            # Check for game updates from HLTB
            results = HowLongToBeat().search(game['GameName'])
            if results and len(results) > 0:
                game_info = results[0]  # Get the first match
                needs_update = False
                
                # Update HLTB time if different
                if hasattr(game_info, 'main_story') and str(game_info.main_story) != str(game['HowLongToBeat']):
                    game['HowLongToBeat'] = str(game_info.main_story)
                    needs_update = True
                
                # Update release year if missing
                if ('ReleaseYear' not in game or not game['ReleaseYear']) and hasattr(game_info, 'release_world'):
                    game['ReleaseYear'] = game_info.release_world
                    needs_update = True
                
                if needs_update:
                    updated_count += 1
        
        save_games(games)
        
        message = []
        if updated_count > 0:
            message.append(f"Updated {updated_count} game{'s' if updated_count != 1 else ''}")
        if cached_count > 0:
            message.append(f"Cached {cached_count} image{'s' if cached_count != 1 else ''}")
        
        if not message:
            message = ["No updates needed"]
            
        return jsonify({"success": True, "message": ". ".join(message)})
        
    except Exception as e:
        logging.error(f"Error updating games: {e}")
        return jsonify({"success": False, "message": "Error updating games"}), 500

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
