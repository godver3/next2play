# next2play

A Flask-based web application to manage your video game backlog. Keep track of games you want to play, their completion status, and how long they take to beat. Uses howlongtobeatpy to fetch game information from HLTB.com. Intended to be simple and no-frills.

![image](https://github.com/user-attachments/assets/e4a2253f-bae8-4f22-bdb9-06eb67c0dd95)


## Features

- Add games to your backlog
- Automatically fetch game information from HowLongToBeat
- Update game statuses (Not Started, In Progress, Completed, Tabled)
- Get suggestions for random games to play
- View currently in-progress games
- Stats for your collection
- Rudimentary password access
- Posters cached locally

![image](https://github.com/user-attachments/assets/96cf0717-70d1-4538-9c03-d3b773858e32)

## Setup

1. Clone the repository
2. Install dependencies: `pip install -r requirements.txt`
3. Run the application: `python app.py`

The app will be available at `http://localhost:5015`.

Alternatively available on docker hub:

```
docker run -d \
  --name next2play \
  -p 5015:5015 \
  -v /path/to/games_data.json:/app/games_data.json \
  -v /path/to/game_images:/app/static/game_images \
  -e ADMIN_PASSWORD=your-password-here \
  -e SECRET_KEY=default-secret-key \
  godver3/next2play:latest
```

## Usage

- Access the main page to view and manage your game backlog
- Use the "Add Game" form to include new titles
- Click on game statuses to update them
- Use the "Random Game" feature for suggestions

## Dependencies

- Flask
- howlongtobeatpy

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.
