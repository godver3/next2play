from flask import Flask, request, render_template, jsonify, session, redirect, url_for
from functools import wraps
import json
import random
import subprocess
import logging
import requests
from bs4 import BeautifulSoup
import time
from howlongtobeatpy import HowLongToBeat
import os
from urllib.parse import urlparse

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')  # Change this in production

# Set up more detailed logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated') and not session.get('view_only'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Edit protection decorator
def edit_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('authenticated'):
            return jsonify({"error": "Authentication required"}), 403
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('password') == os.environ.get('ADMIN_PASSWORD', 'your-password-here'):
            session['authenticated'] = True
            return redirect(url_for('index'))
        return render_template('login.html', error='Invalid password')
    return render_template('login.html')

@app.route('/view_only', methods=['POST'])
def view_only():
    session['view_only'] = True
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

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
@login_required
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

    is_view_only = session.get('view_only', False)
    return render_template('index.html', games=games, sort_column=sort_column, sort_order=sort_order, is_view_only=is_view_only)

@app.route('/add_game', methods=['POST'])
@edit_required
def add_game():
    try:
        data = request.get_json()
        logger.debug("Parsed JSON data: %s", data)
        
        if not data:
            return jsonify({'success': False, 'message': 'No JSON data received'}), 400
            
        search_term = data.get('GameName')
        if not search_term:
            return jsonify({'success': False, 'message': 'GameName is required'}), 400
            
        submitted_id = int(data['GameID'])
        
        # Search using the library
        results = HowLongToBeat().search(search_term)
        
        if results:
            # Find the specific game version that was selected
            game_info = next((game for game in results if game.game_id == submitted_id), None)
            
            if game_info:
                game_id = game_info.game_id
                game_name = game_info.game_name
                
                # Fix image URL handling
                image_url = game_info.game_image_url
                if image_url and not image_url.startswith('http'):
                    image_url = f"https://howlongtobeat.com{image_url}"
                
                # Get completion time
                how_long_to_beat = None
                if hasattr(game_info, 'main_story') and game_info.main_story:
                    how_long_to_beat = round(float(game_info.main_story))
                
                # Get release year
                release_year = None
                if hasattr(game_info, 'release_world') and game_info.release_world:
                    release_year = int(game_info.release_world)

                games = load_games()

                # Check for duplicate
                existing_game = next(
                    (game for game in games 
                     if game['GameName'] == game_name 
                     and game['ReleaseYear'] == release_year), 
                    None
                )

                if existing_game:
                    return jsonify({
                        'success': False,
                        'message': 'This game is already in your collection'
                    }), 409
                
                # Cache the image locally
                cached_image_url = download_and_cache_image(image_url, game_id) if image_url else ''
                logger.info("Original image URL: %s", image_url)
                logger.info("Cached image URL: %s", cached_image_url)
                
                new_game = {
                    "GameID": game_id,
                    "GameName": game_name,
                    "HowLongToBeat": how_long_to_beat or "Unreleased",
                    "ProgressStatus": "Not Started",
                    "ImageURL": cached_image_url or '',
                    "ReleaseYear": release_year
                }
                
                logger.info("Saving game with data: %s", new_game)
                
                games.append(new_game)
                save_games(games)
                return jsonify({
                    'success': True,
                    'message': 'Game added successfully',
                    'game': new_game
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'message': 'Selected game version not found'
                }), 404
        else:
            return jsonify({
                'success': False,
                'message': 'Game not found'
            }), 404
    except Exception as e:
        logger.error("Unexpected error in add_game: %s", str(e))
        return jsonify({
            'success': False,
            'message': f'Error adding game: {str(e)}'
        }), 500

@app.route('/update_games', methods=['POST'])
@edit_required
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
@edit_required
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
@edit_required
def update_status(game_id):
    try:
        data = request.json
        new_status = data.get('status')
        
        if not new_status:
            return jsonify({"success": False, "message": "Status is required"}), 400

        games = load_games()
        game_found = False
        for game in games:
            if game['GameID'] == game_id:
                game['ProgressStatus'] = new_status
                game_found = True
                break
                
        if not game_found:
            return jsonify({"success": False, "message": "Game not found"}), 404
            
        save_games(games)
        return jsonify({"success": True, "message": "Status updated successfully"})

    except Exception as e:
        logger.error(f"Error updating status: {str(e)}")
        return jsonify({"success": False, "message": "Error updating status"}), 500


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
        
        logger.debug(f"Searching for term: {search_term}")
        
        # Use the HowLongToBeat library to search
        results = HowLongToBeat().search(search_term)
        
        if results:
            games_data = []
            for game in results:
                # Fix image URL construction
                image_url = game.game_image_url
                if image_url and not image_url.startswith('http'):
                    image_url = f"https://howlongtobeat.com{image_url}"
                
                # Get main story time in hours
                main_story_hours = game.main_story if hasattr(game, 'main_story') else None
                if main_story_hours:
                    main_story_hours = round(float(main_story_hours))
                
                game_data = {
                    'game_id': game.game_id,
                    'game_name': game.game_name,
                    'game_image_url': image_url,
                    'release_world': game.release_world if hasattr(game, 'release_world') else None,
                    'main_story': main_story_hours
                }
                games_data.append(game_data)
            
            logger.debug(f"Found {len(games_data)} games")
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

def get_hltb_user_id():
    # Placeholder implementation
    # Replace with actual logic to retrieve the user ID if needed
    return 1

@app.route('/stats')
@login_required
def stats():
    games = load_games()
    
    # Calculate statistics
    stats = {
        'total_games': len(games),
        'completed_games': len([g for g in games if g['ProgressStatus'] == 'Complete']),
        'in_progress_games': len([g for g in games if g['ProgressStatus'] == 'In Progress']),
        'not_started_games': len([g for g in games if g['ProgressStatus'] == 'Not Started']),
        'tabled_games': len([g for g in games if g['ProgressStatus'] == 'Tabled']),
        'total_hours_completed': sum(float(g['HowLongToBeat']) for g in games 
                                   if g['ProgressStatus'] == 'Complete' 
                                   and g['HowLongToBeat'] != 'Unreleased'),
        'total_hours_remaining': sum(float(g['HowLongToBeat']) for g in games 
                                   if g['ProgressStatus'] == 'Not Started' 
                                   and g['HowLongToBeat'] != 'Unreleased'),
        'total_hours_in_progress': sum(float(g['HowLongToBeat']) for g in games 
                                     if g['ProgressStatus'] == 'In Progress' 
                                     and g['HowLongToBeat'] != 'Unreleased')
    }
    
    return render_template('stats.html', stats=stats)

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=5015)
