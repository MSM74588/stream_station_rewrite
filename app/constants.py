import os
from .utils.resource_fetchers import load_config
from pathlib import Path
import re

MPD_PORT = "6601"
BASE_DIR = Path(__file__).resolve().parent


YTDLP_DOWNLOAD_DIR = BASE_DIR / "media" / "downloads" / "youtube"
SPOTDL_DOWNLOAD_DIR = BASE_DIR / "media" / "downloads" / "spotify"

# THIS NEEDS REFACTORING

CONFIG_PATH = BASE_DIR / "configs" / "config.yaml"
AUTH_PATH = BASE_DIR / "configs" / "spotify_auth.yaml"
SPOTIFY_DB_PATH = BASE_DIR / "db" / "spotify_liked_songs.db"
# LIKED_SONGS_DB_PATH = BASE_DIR / "db" / "liked_songs.db"
SPOTIFY_SCOPES = "user-library-read user-read-playback-state user-modify-playback-state"
VERSION = "0.1.0"
MUSIC_DIR = BASE_DIR / "media"

IGNORE_PLAYERS = "Gwenview,firefox,GSConnect"

config = load_config(CONFIG_PATH)
SPOTIFY_MODE = config["spotify_mode"]
CONTROL_MODE = config["control_mode"]


REQUIRED_EXECUTABLES = ["yt-dlp", "mpv", "mpd", "mpc", "mpDris2", "playerctl", "ffmpeg"]

COVER_ART_PATH = Path(__file__).resolve().parent / "assets" / "coverarts"
COVER_ART_URL_PREFIX = "/assets/coverarts"

DATABASE_URL = "sqlite:///db/app.db"

SPOTIFY_URL_PATTERN = re.compile(r'https://open\.spotify\.com/(track|episode)/([a-zA-Z0-9]+)')