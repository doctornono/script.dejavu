# dejaVu integration for Kodi

Professional integration of [dejaVu.plus](https://dejavu.plus) for Kodi. Sync your watch history, watchlist, and ratings seamlessly.

## Features

- **Automatic Scrobbling**: Real-time playback synchronization (defaults to 90% threshold for "watched" status).
- **Ratings Synchronization**: Rate movies and TV shows directly from Kodi.
- **Unified History**: Keeps your dejavu.plus history in sync with your local playback.
- **Device Code Login**: Secure OAuth 2.0 login flow (no password needed in Kodi).
- **Background Service**: Synchronizes in the background for a seamless experience.

## Installation

1.  Download the repository as a ZIP.
2.  In Kodi, go to **Add-ons** > **Install from zip file**.
3.  Navigate to the downloaded ZIP and install.

## Configuration

1.  Open **Add-on settings**.
2.  Click **Login with dejaVu**.
3.  Visit [dejavu.plus/activate](https://dejavu.plus/activate) and enter the code displayed in Kodi.
4.  Optionally, adjust the **Watched %** threshold in the Scrobbling section (default 90%).

## For Developers (RPC API)

This addon exposes a rich JSON-RPC interface for other addons to interact with:
- `script.dejavu.get_history`
- `script.dejavu.add_to_history`
- `script.dejavu.rate`
- ... (Total of 14 actions)

## License

This project is licensed under the MIT License - see the [LICENSE.txt](LICENSE.txt) file for details.
