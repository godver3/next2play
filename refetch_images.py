import os
import json
import logging
import requests
import subprocess
from pathlib import Path
from howlongtobeatpy import HowLongToBeat

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def load_games():
    """Load games from the JSON database"""
    games_file = Path('games_data.json')
    if not games_file.exists():
        return []
    with open(games_file, 'r') as f:
        return json.load(f)

def refetch_images():
    """Refetch and reprocess all game images"""
    try:
        # Get all games from the database
        games = load_games()
        total = len(games)
        processed = 0
        failed = 0
        
        logger.info(f"Found {total} games to process")
        hltb = HowLongToBeat()
        
        for game in games:
            try:
                game_name = game['GameName']
                game_id = game['GameID']
                
                logger.info(f"Processing {game_id}: {game_name}")
                
                # Search for the game on HLTB
                results = hltb.search(game_name)
                if not results:
                    logger.error(f"No results found for {game_name}")
                    failed += 1
                    continue
                
                # Find the specific game version
                game_info = next((g for g in results if g.game_id == game_id), None)
                if not game_info:
                    logger.error(f"Couldn't find exact match for {game_name} (ID: {game_id})")
                    failed += 1
                    continue
                
                # Get the image URL
                image_url = game_info.game_image_url
                if image_url and not image_url.startswith('http'):
                    image_url = f"https://howlongtobeat.com{image_url}"
                
                if not image_url:
                    logger.error(f"No image URL found for {game_name}")
                    failed += 1
                    continue
                
                # Get the relative and local paths
                relative_path = os.path.join('game_images', f'game_{game_id}.jpg')
                local_path = os.path.join('static', relative_path)
                
                # Create game_images directory if it doesn't exist
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                
                # Download and process the image
                response = requests.get(image_url, stream=True)
                if response.status_code == 200:
                    # Save to temp file first
                    temp_path = local_path + '.temp'
                    with open(temp_path, 'wb') as f:
                        f.write(response.content)
                    
                    # Process with ImageMagick
                    subprocess.run([
                        'convert', temp_path,
                        '-resize', '200x300>',
                        '-quality', '90',
                        '-strip',
                        '-interlace', 'Plane',
                        local_path
                    ], check=True)
                    
                    # Clean up temp file
                    if os.path.exists(temp_path):
                        os.remove(temp_path)
                    
                    processed += 1
                    logger.info(f"Successfully processed {game_name}")
                    
                else:
                    logger.error(f"Failed to download image for {game_name}: HTTP {response.status_code}")
                    failed += 1
                    
            except Exception as e:
                logger.error(f"Error processing {game_name}: {str(e)}")
                failed += 1
                continue
        
        logger.info("\nProcessing Complete!")
        logger.info(f"Successfully processed: {processed}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Total games: {total}")
        
    except Exception as e:
        logger.error(f"Error during refetch: {str(e)}")

if __name__ == '__main__':
    refetch_images()
