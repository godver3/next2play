// Global variables and event listeners
document.addEventListener('DOMContentLoaded', () => {
    sortGames();
    renderGames();
    loadFilters();
    
    if (!IS_VIEW_ONLY) {
        setupEventListeners();
    }
});

function setupEventListeners() {
    // Add game form submission
    document.getElementById('GameName').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            submitGameForm();
        }
    });
}

// Game Management Functions
async function submitGameForm() {
    const gameName = document.getElementById('GameName').value.trim();
    if (!gameName) return;

    const payload = { GameName: gameName };
    console.log('Sending payload:', payload); // Debug log

    try {
        const response = await fetch('/search_games', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorText = await response.text();
            console.error('Server response:', errorText);
            throw new Error(`Network response was not ok: ${errorText}`);
        }

        const games = await response.json();
        if (games && games.length > 0) {
            showGameSelection(games.map(game => ({
                id: game.game_id,
                name: game.game_name,
                image_url: game.game_image_url,
                release_date: game.release_world,
                hltb: game.main_story
            })));
        } else {
            showNotification('No games found', 'error');
        }
    } catch (error) {
        showNotification('Error searching for game', 'error');
        console.error('Error:', error);
    }
}

async function updateProgressStatus(gameId, newStatus) {
    try {
        const response = await fetch(`/update_status/${gameId}`, {  // Updated URL
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                status: newStatus
            })
        });

        if (!response.ok) throw new Error('Network response was not ok');

        const data = await response.json();
        if (data.success) {
            showNotification('Status updated successfully!', 'success');
            // Update local games array
            const game = games.find(g => g.GameID === gameId);
            if (game) {
                game.ProgressStatus = newStatus;
                updateGameCardStatus(gameId, newStatus);
            }
            setTimeout(() => {
                window.location.reload();
            }, 1000); // Wait 1 second before refreshing
        } else {
            showNotification('Failed to update status', 'error');
        }
    } catch (error) {
        showNotification('Error updating status', 'error');
        console.error('Error:', error);
    }
}

async function deleteGame(gameId) {
    if (!confirm('Are you sure you want to delete this game?')) return;

    try {
        const response = await fetch(`/delete_game/${gameId}`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) throw new Error('Network response was not ok');

        const data = await response.json();
        if (data.success) {
            showNotification('Game deleted successfully!', 'success');
            // Remove from local games array and DOM
            games = games.filter(g => g.GameID !== gameId);
            const gameCard = document.querySelector(`[data-game-id="${gameId}"]`);
            if (gameCard) gameCard.remove();
        } else {
            showNotification('Failed to delete game', 'error');
        }
    } catch (error) {
        showNotification('Error deleting game', 'error');
        console.error('Error:', error);
    }
}

async function getRandomGame() {
    // Filter to only "Not Started" games, then apply any other active filters
    const notStartedGames = filterGames().filter(game => game.ProgressStatus === 'Not Started');
    
    if (notStartedGames.length === 0) {
        showNotification('No unstarted games available', 'error');
        return;
    }

    const randomIndex = Math.floor(Math.random() * notStartedGames.length);
    const selectedGame = notStartedGames[randomIndex];
    
    showNotification(`Random game selected: ${selectedGame.GameName}`, 'success');
    highlightGame(selectedGame.GameID);
}

async function updateGames() {
    try {
        const response = await fetch('/update_games', {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Network response was not ok');

        const data = await response.json();
        if (data.success) {
            showNotification('Games updated successfully!', 'success');
            window.location.reload();
        } else {
            showNotification('Failed to update games', 'error');
        }
    } catch (error) {
        showNotification('Error updating games', 'error');
        console.error('Error:', error);
    }
}

// UI Helper Functions
function showNotification(message, type) {
    const notificationBar = document.getElementById('notificationBar');
    notificationBar.textContent = message;
    notificationBar.className = `notification ${type}`;
    notificationBar.style.display = 'block';

    // Automatically hide after 3 seconds
    setTimeout(() => {
        notificationBar.style.display = 'none';
    }, 3000);
}

function updateGameCardStatus(gameId, newStatus) {
    const gameCard = document.querySelector(`[data-game-id="${gameId}"]`);
    if (gameCard) {
        // Remove all status classes
        gameCard.classList.forEach(className => {
            if (className.startsWith('status-')) {
                gameCard.classList.remove(className);
            }
        });
        // Add new status class
        gameCard.classList.add(`status-${newStatus.replace(' ', '-').toLowerCase()}`);
    }
}

function highlightGame(gameId) {
    // Remove highlight from all games
    document.querySelectorAll('.game-card').forEach(card => {
        card.classList.remove('highlighted');
    });

    // Add highlight to selected game
    const gameCard = document.querySelector(`[data-game-id="${gameId}"]`);
    if (gameCard) {
        gameCard.classList.add('highlighted');
        gameCard.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

// Game Selection Popup Functions
function showGameSelection(gameOptions) {
    const popup = document.getElementById('gameSelectionPopup');
    const optionsContainer = document.getElementById('gameOptions');
    optionsContainer.innerHTML = '';

    gameOptions.forEach(game => {
        const option = document.createElement('div');
        option.className = 'game-option';
        option.innerHTML = `
            <img src="${game.image_url}" alt="${game.name}" class="game-option-image">
            <div class="game-option-info">
                <div class="game-option-name">${game.name}</div>
                <div class="game-option-details">
                    ${game.platform ? `<span>Platform: ${game.platform}</span>` : ''}
                    ${game.release_date ? `<span>Release: ${game.release_date}</span>` : ''}
                </div>
            </div>
        `;
        option.onclick = () => selectGame(game.id);
        optionsContainer.appendChild(option);
    });

    popup.style.display = 'flex';
}

function closeGameSelection() {
    document.getElementById('gameSelectionPopup').style.display = 'none';
}

async function selectGame(gameId) {
    try {
        const response = await fetch('/add_game', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                GameID: gameId,
                GameName: document.getElementById('GameName').value.trim(),
                ReleaseYear: null,
                HowLongToBeat: null
            })
        });

        // Check if it's a duplicate game (409 status)
        if (response.status === 409) {
            showNotification('This game is already in your collection', 'warning');
            closeGameSelection();
            return;
        }

        if (!response.ok) throw new Error('Network response was not ok');

        // Show notification and wait briefly before refreshing
        showNotification('Game added successfully!', 'success');
        document.getElementById('GameName').value = '';
        setTimeout(() => {
            window.location.reload();
        }, 1000); // Wait 1 second before refreshing

    } catch (error) {
        showNotification('Error adding game', 'error');
        console.error('Error:', error);
    } finally {
        closeGameSelection();
    }
}

// Game Rendering and Filtering Functions
function renderGames() {
    const gameGrid = document.getElementById('game-grid');
    gameGrid.innerHTML = '';

    const filteredGames = filterGames();
    
    filteredGames.forEach(game => {
        const gameCard = document.createElement('div');
        gameCard.className = `game-card status-${game.ProgressStatus.toLowerCase().replace(' ', '-')}`;
        gameCard.dataset.gameId = game.GameID;

        gameCard.innerHTML = `
            ${game.ReleaseYear ? `<div class="release-year">${game.ReleaseYear}</div>` : ''}
            <img src="${game.ImageURL}" alt="${game.GameName}" class="game-poster">
            <div class="game-info">
                <div class="game-title">${game.GameName}</div>
                <div class="game-hltb">How Long to Beat: ${game.HowLongToBeat}</div>
                ${!IS_VIEW_ONLY ? `
                    <select onchange="updateProgressStatus(${game.GameID}, this.value)">
                        <option value="Not Started" ${game.ProgressStatus === 'Not Started' ? 'selected' : ''}>Not Started</option>
                        <option value="In Progress" ${game.ProgressStatus === 'In Progress' ? 'selected' : ''}>In Progress</option>
                        <option value="Complete" ${game.ProgressStatus === 'Complete' ? 'selected' : ''}>Complete</option>
                        <option value="Tabled" ${game.ProgressStatus === 'Tabled' ? 'selected' : ''}>Tabled</option>
                    </select>
                    <button onclick="deleteGame(${game.GameID})">Delete</button>
                ` : ''}
            </div>
        `;

        gameGrid.appendChild(gameCard);
    });
}

function filterGames() {
    let filteredGames = [...games];
    const statusFilter = document.getElementById('statusFilter')?.value;
    const searchFilter = document.getElementById('searchFilter')?.value?.toLowerCase();

    if (statusFilter && statusFilter !== 'All') {
        filteredGames = filteredGames.filter(game => game.ProgressStatus === statusFilter);
    }

    if (searchFilter) {
        filteredGames = filteredGames.filter(game => 
            game.GameName.toLowerCase().includes(searchFilter)
        );
    }

    return filteredGames;
}

function loadFilters() {
    const statusFilter = document.getElementById('statusFilter');
    const searchFilter = document.getElementById('searchFilter');

    if (statusFilter) {
        statusFilter.addEventListener('change', renderGames);
    }
    
    if (searchFilter) {
        searchFilter.addEventListener('input', renderGames);
    }
}

function sortGames() {
    games.sort((a, b) => {
        // First, compare status ("In Progress" comes first)
        if (a.ProgressStatus === 'In Progress' && b.ProgressStatus !== 'In Progress') return -1;
        if (b.ProgressStatus === 'In Progress' && a.ProgressStatus !== 'In Progress') return 1;
        
        // If both games have the same status (or neither is "In Progress"),
        // sort alphabetically by name
        return a.GameName.localeCompare(b.GameName);
    });
}

