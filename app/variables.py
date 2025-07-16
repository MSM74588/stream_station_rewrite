from .models import PlayerInfo, MediaInfo, LastPlayedMedia
from typing import Optional, Any, Dict, List
from .players.mpvplayer import MPVMediaPlayer
import subprocess

# INITIALISE, AND USE THIS FOR STATE MANAGEMENT
player_info = PlayerInfo(
    is_paused=False,
    cache_size=0,
    media_duration=0,
    media_progress=0
)

player_type: str = ""

media_info = MediaInfo()

last_played_media = LastPlayedMedia(title="", url="")

player_instance: Optional[MPVMediaPlayer] = None

mpd_proc: subprocess.Popen | None = None
mpdirs2_proc: subprocess.Popen | None = None