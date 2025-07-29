import requests
import subprocess
import sys
from pathlib import Path

# === Constants ===
BASE_URL = "localhost"
PORT = "8000"
SPOTIFY_SONGS_ENDPOINT = f"http://{BASE_URL}:{PORT}/songs/spotify"

# Path where final downloaded files should go
DOWNLOAD_DIR = Path("./app/media/downloads/spotify")

def ensure_directories():
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

def fetch_favourite_spotify_urls():
    try:
        response = requests.get(SPOTIFY_SONGS_ENDPOINT)
        response.raise_for_status()
        data = response.json()

        urls = []
        for item in data:
            url = item.get("spotify_url")
            if url:
                urls.append(url)
            else:
                print(f"⛔ Skipping item (no spotify_url): {item}")

        print(f"🔎 Found {len(urls)} Spotify tracks in favourites.")
        return urls

    except requests.RequestException as e:
        print(f"❌ Failed to fetch favourites: {e}")
        sys.exit(1)

def download_track(spotify_url):
    print(f"🎵 Downloading: {spotify_url}")
    try:
        result = subprocess.run(
            [
                "spotdl",
                "--output", str(DOWNLOAD_DIR),  # just the directory, not full template
                spotify_url
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if result.returncode != 0:
            print(f"⚠️ Error downloading {spotify_url}:\n{result.stderr}")
        else:
            print(f"✅ Downloaded: {spotify_url}")
    except FileNotFoundError:
        print("❌ 'spotdl' is not found in PATH. Make sure it is installed.")
        sys.exit(1)

def main():
    ensure_directories()
    urls = fetch_favourite_spotify_urls()
    for url in urls:
        download_track(url)

if __name__ == "__main__":
    main()
