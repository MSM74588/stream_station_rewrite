import shutil
import subprocess
import json
import re
from typing import Optional
from app.models import MediaInfo

from ..variables import media_info


def check_ytdlp_available():
    return shutil.which("yt-dlp") is not None

def get_media_data(url: str) -> Optional[MediaInfo]:
    try:
        if not check_ytdlp_available():
            print("yt-dlp not available")
            # LOG this error or handle it as needed
            raise ValueError("yt-dlp is not installed or not found in PATH")

        cmd = ["yt-dlp", "-j", url]  # -j = print metadata as JSON
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=60)
        
        if result.returncode != 0:
            raise ValueError(f"yt-dlp error: {result.stderr.strip()}")


            
        data = json.loads(result.stdout)

        if not data:
            raise ValueError("No metadata found for the provided URL")
                
        return data
    except subprocess.TimeoutExpired:
        print("yt-dlp metadata fetch timed out")
        return None
    except Exception as e:
        print(f"Error fetching media info: {e}")
        return None
    
def extract_youtube_id(url: str) -> str | None:
    # Match typical YouTube URL formats
    patterns = [
        r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([^\s&]+)",
        r"(?:https?://)?youtu\.be/([^\s?/]+)",
        r"(?:https?://)?(?:www\.)?youtube\.com/embed/([^\s?/]+)"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None
