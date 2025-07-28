import subprocess
import json
from typing import Optional, List
from app.constants import SPOTIFY_URL_PATTERN
from app.models import SongMetadataModel
from urllib.parse import urlparse, parse_qs, urlunparse

from .spotify_auth_utils import load_spotify_auth

def clean_youtube_url(url: str) -> Optional[str]:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    video_id = query.get("v", [None])[0]

    if not video_id:
        return None

    clean_query = f"v={video_id}"
    cleaned_url = urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        '',                # params
        clean_query,       # query
        ''                 # fragment
    ))
    return cleaned_url


def get_youtube_metadata(youtube_url: str) -> Optional[SongMetadataModel]:
    try:
        # Clean the URL to retain only video ID and same domain
        clean_url = clean_youtube_url(youtube_url)
        if not clean_url:
            print("Invalid YouTube URL.")
            return None

        # Fetch metadata using yt-dlp
        cmd = ["yt-dlp", "-j", clean_url]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        return SongMetadataModel(
            media_name=data.get("title"),
            artist=data.get("uploader"),
            album=None,
            source="youtube",
            duration=data.get("duration"),  # already in seconds
            url=clean_url  # optionally include cleaned URL
        )

    except subprocess.CalledProcessError as e:
        print("Error fetching metadata with yt-dlp:", e)
        return None
    except Exception as e:
        print("Unexpected error:", e)
        return None

    
def get_mpd_by_metadata(song_name: str) -> List[SongMetadataModel]:

    if not song_name:
        raise ValueError("Song Name not Provided")

    cmd = ["mpc", "-f", "%title%\n%artist%\n%album%\n%time%", "search", "title", song_name]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        lines = result.stdout.strip().split("\n")

        songs = []
        for i in range(0, len(lines), 4):
            chunk = lines[i:i+4]
            if len(chunk) < 4:
                continue
            title, artist, album, duration_str = map(str.strip, chunk)
            try:
                minutes, seconds = map(int, duration_str.split(":"))
                duration = minutes * 60 + seconds
            except:
                duration = None

            songs.append(SongMetadataModel(
                media_name=title,
                artist=artist,
                album=album,
                duration=duration,
                source="mpd",
                url=""
            ))

        return songs

    except subprocess.CalledProcessError as e:
        print("Error running mpc:", e)
        return []


def get_spotify_info(url: str) -> SongMetadataModel:
    """
    Fetch metadata for Spotify track or episode using existing OAuth credentials.
    """
    match = SPOTIFY_URL_PATTERN.match(url)
    if not match:
        raise ValueError("Invalid Spotify URL format")

    item_type, item_id = match.groups()

    try:
        sp = load_spotify_auth()
    except Exception as e:
        raise ValueError("Spotify not authenticated. Please run /setup to login.")

    if item_type == "track":
        data = sp.track(item_id)
        return SongMetadataModel(
            media_name=data["name"],
            artist=", ".join(artist["name"] for artist in data["artists"]),
            album=data["album"]["name"],
            duration=int(data["duration_ms"] / 1000),
            source="spotify",
            url=url
        )

    elif item_type == "episode":
        data = sp.episode(item_id)
        return SongMetadataModel(
            song_name=data["name"],
            artist=data["show"]["publisher"],  # e.g., podcast publisher
            album=data["show"]["name"],         # podcast name
            duration=int(data["duration_ms"] / 1000),
            source="spotify",
            url=url
        )

    else:
        raise ValueError("Unsupported Spotify item type")