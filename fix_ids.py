import json

def load_games():
    with open('games_data.json', 'r') as f:
        return json.load(f)

def save_games(games):
    with open('games_data.json', 'w') as f:
        json.dump(games, f, indent=2)

def fix_game_ids():
    games = load_games()
    updated_count = 0

    for game in games:
        if not isinstance(game['GameID'], int):
            try:
                game['GameID'] = int(game['GameID'])
                updated_count += 1
            except ValueError:
                print(f"Warning: Could not convert GameID to integer for game: {game['GameName']}")

    save_games(games)
    print(f"Updated {updated_count} game IDs")

if __name__ == "__main__":
    fix_game_ids()
