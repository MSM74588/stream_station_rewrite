from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, HttpUrl
from app.constants import YTDLP_DOWNLOAD_DIR, SPOTDL_DOWNLOAD_DIR
import subprocess
import re
from pathlib import Path

router = APIRouter()

YTDLP_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
SPOTDL_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

class DownloadRequest(BaseModel):
    url: HttpUrl

def resolve_spotify_share_link(url: str) -> str:
    """Resolves Spotify short share links to their final URLs using curl."""
    try:
        result = subprocess.run(
            ["curl", "-Ls", "-o", "/dev/null", "-w", "%{url_effective}", url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
            text=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=400, detail="Failed to resolve share link")

def run_download(url: str):
    youtube_pattern = re.compile(r"(https?://)?(www\.)?(music\.)?youtube\.com|youtu\.be")
    spotify_pattern = re.compile(r"(https?://)?(open\.)?spotify\.com")
    spotify_short_pattern = re.compile(r"(https?://)?(spoti\.fi|spotify\.link)/")

    try:
        # Resolve short Spotify links
        if spotify_short_pattern.search(url):
            url = resolve_spotify_share_link(url)

        if youtube_pattern.search(url):
            output_template = str(YTDLP_DOWNLOAD_DIR / "%(title)s.%(ext)s")
            command = [
                "yt-dlp",
                "-f", "bestaudio",
                "-o", output_template,
                "--extract-audio",
                "--audio-format", "mp3",
                url
            ]
            subprocess.run(command, check=True)

        elif spotify_pattern.search(url):
            command = [
                "spotdl",
                "--output", str(SPOTDL_DOWNLOAD_DIR),
                url
            ]
            subprocess.run(command, check=True)

    except subprocess.CalledProcessError:
        # Logging or error tracking can be added here
        pass

@router.post("/download")
async def download_audio(request: DownloadRequest, background_tasks: BackgroundTasks):
    url = str(request.url)

    youtube_pattern = re.compile(r"(https?://)?(www\.)?(music\.)?youtube\.com|youtu\.be")
    spotify_pattern = re.compile(r"(https?://)?(open\.)?spotify\.com")
    spotify_short_pattern = re.compile(r"(https?://)?(spoti\.fi|spotify\.link)/")

    # Pre-check for support
    if not (youtube_pattern.search(url) or spotify_pattern.search(url) or spotify_short_pattern.search(url)):
        return {"status": "unsupported", "message": "URL is not supported for download."}

    # Schedule download task
    background_tasks.add_task(run_download, url)
    return {"status": "scheduled", "message": "Download has been scheduled."}
