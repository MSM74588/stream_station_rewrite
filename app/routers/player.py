from fastapi import APIRouter
from fastapi import Body, Query

# from ..variables import player_instance, media_info
import app.variables as vars

from ..models import PlayerInfo, MediaData

from typing import Optional
from fastapi.exceptions import HTTPException

import subprocess
from pathlib import Path
from urllib.parse import urlparse, unquote
from fastapi.responses import Response
import requests

from app.utils.media_handlers import *





# NAME IT WHATEVER YOU WANT, PLAYER_ROUTER IS JUST A SUGGESTION
router = APIRouter()



"""
TODO: Queue
- This has to be handled as per the link (if playlist link) provided, like if spotify is instructed to play a Playlist,
It should not initiate the queue, and the next and previous action should be directly be passed to mpris player to play the next song in the play list.
"""


@router.get("/", tags=["Player"], summary="Get Player Status", response_model=PlayerInfo)
def player_status():
    """
    # Player Status
    Gets the current status of the media player -> `vars.player_instance`.
    """
    
        
    if vars.player_instance is not None:
        vars.player_info = vars.player_instance.get_state()
        return vars.player_info
    
@router.post("/play", tags=["Player"])
async def play_media(MediaData: Optional[MediaData] = Body(None)):
    """
    # Play Media
    if `vars.player_instance` is not `None` i.e,  a player is loaded, then it triggers `play` action of player regardless if its paused
    or not.

    else, if `vars.player_instance` is `None`, i.e no player loaded, then it takes either an `url` or `song_name`.
    It first processes `song_name` and if `song_name` is there, then it will play `MPD`
    
    if `url` is provided then:
    1. <b>spotify</b> will be played by `SpotifyMPRISPlayer`
    2. <b>Youtube</b> will be played by `MPVMediaPlayer`
    3. Then if any `unknown_url` is passed it will be handled via the `browser_url_handler` as per links mentioned in `url_handler.yaml` TODO
    4. Ultimately in case if no match, it will return an `HTTPException`
    """
    
        
    def _clean_player(player):
        try:
            if player is not None:
                player.unload()  # Gracefully unload the player (stop, cleanup, etc.)
            vars.player_instance = None  # Explicitly reset global reference
        except Exception as e:
            print(f"Cannot Stop Player: {e}")
            raise ValueError("Cannot Stop Player")
    
    # PLAIN PLAYBACK CONTROL, IF NOT DATA IS PASSED
    if vars.player_instance is not None and not MediaData:
        # CAN BE MPRIS, MPD, MPV
        vars.player_instance.play()
        return {
            "message" : "played"
        }
        
        
    # IF PLAYER_INSTANCE is Empty, then Check if the DATA is complete, to be played 
    if MediaData is None or (not MediaData.url and not MediaData.song_name):
        raise HTTPException(status_code=400, detail="Media URL or song name is required.")
    
    # MPD PLAYBACK -----------------------------------------------------------------
    
    # if it contains song_name then route to MPD playback, for local playback only. 
    if MediaData.song_name and not MediaData.url:
        song_name = MediaData.song_name.strip()
        return await handle_mpd_song(song_name, _clean_player)

        
    url = MediaData.url.strip() # type: ignore
    
    
    
    # === Dispatcher ===
        
    handlers = [
        (is_spotify_url, handle_spotify_url),
        (is_youtube_url, handle_youtube_url),
    ]

    for matcher, handler in handlers:
        if matcher(url):
            return await handler(url, _clean_player)

    raise HTTPException(status_code=400, detail="Unsupported media URL. Only Spotify and YouTube URLs are supported.")
    
# ======== MEDIA MATHERS ============

def is_spotify_url(url: str) -> bool:
    return "spotify.com" in url

def is_youtube_url(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url

# ================ MEDIA HANDLERS ==================== #
    
    
@router.post("/stop", tags=["Player"])
def stop_player():
    """
    # Stops Player
    Stops Player and Unloads them from `vars.player_instance`
    """

    if vars.player_instance is None:
            raise HTTPException(status_code=400, detail="No media is currently loaded")
    try:
        vars.player_instance.stop()
        vars.player_instance = None  # Reset the player instance                
        # Reset the STATE
        vars.player_info = PlayerInfo()
        vars.player_info.status = "stopped"
        return vars.player_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute stop: {str(e)}")
    

@router.post("/pause", tags=["Player"])
def pause_player():
    """
    # Pause the current player
    """

    if vars.player_instance is None:
        raise HTTPException(status_code=400, detail="No media is currently loaded")
    
    try:
        vars.player_instance.pause()
        vars.player_info = vars.player_instance.get_state()
        # player_info. = PlayerInfo(is_paused=True)
        
        return vars.player_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute pause: {str(e)}")
    
    
@router.post("/loop", tags=["Player"])
def loop_player():
    """
    # Set Loop Mode of Player
    Toggles the loop mode for the player, it only sets track loop mode, i.e single loop for ALL types of players.
    """
    if vars.player_instance is not None:
        
            # SET MPD REPEAT MODE
        return {
            "loop enabled": vars.player_instance.set_repeat(),
        }
        
    else:
        raise HTTPException(status_code=400, detail="No media is currently loaded")
    
@router.post("/volume", tags=["Player"])
def set_volume(set: int = Query(..., ge=0, le=150, description="Volume percent (0-150)")):
    """
    # Set Volume of player
    Pass the volume as a parameter, and it sets the volume.
    For `MPV` the volume can be set upto `150`, for others it is capped to 100
    """
    
    if vars.player_instance is None:
        raise HTTPException(status_code=400, detail="No media is currently loaded")
    
    if not (0 <= set <= 150):
            raise HTTPException(status_code=400, detail="Volume must be between 0 and 150")
        
    if vars.player_instance.type == "mpd" or vars.player_instance.type == "spotify":
        # Cap set to 100 for mpd
        set = min(set, 100)
        
    vars.player_instance.set_volume(set)
                
    vars.player_info = vars.player_instance.get_state()
    return vars.player_info


# TODO: Implement with Queue and playback listener and manager
@router.post("/next", tags=["Player"])
def player_next():
    """
    # Play Next Track from `Queue`
    TODO
    """
    return {"message": "TODO: player next"}
    
@router.post("/previous", tags=["Player"])
def player_previous():
    """
    # Play Next Track from `Queue`
    TODO
    """
    return {"message": "TODO: player prev"}


@router.get("/album_art", tags=["Player"])
def album_art():
    """
    # Album Art
    Returns the album art image.
    Uses MPRIS to get the metadata `mpris:artUrl`
    If no player is running, i.e `vars.player_instance` is `None`, returns an HTTPException
    """


    valid_states_by_player = {
        "spotify": ["playing", "paused"],
        "mpd": ["playing"],
        "mpv": ["playing", "paused"]  # if supported via playerctl
    }

    valid_states = valid_states_by_player.get(vars.player_type, [])

    try:
        status = subprocess.check_output(
            ["playerctl", "--player=" + vars.player_type, "status"],
            text=True
        ).strip().lower()
        print(f"{vars.player_type} status: {status}")

        if status not in valid_states:
            return {"error": f"{vars.player_type} not in a valid state"}

        url = subprocess.check_output(
            ["playerctl", "--player=" + vars.player_type, "metadata", "mpris:artUrl"],
            text=True
        ).strip()
        print(f"{vars.player_type} artUrl: {url}")

        if url.startswith("file://"):
            parsed = urlparse(url)
            local_path = Path(unquote(parsed.path))
            print(f"Trying local path: {local_path}")

            if not local_path.exists():
                return {"error": "File not found at local path"}

            mime = "image/jpeg"
            if local_path.suffix.lower() == ".png":
                mime = "image/png"

            return Response(content=local_path.read_bytes(), media_type=mime)

        elif url.startswith("http"):
            print(f"Downloading remote image from: {url}")
            response = requests.get(url, timeout=5)

            if response.status_code != 200:
                return {"error": f"HTTP request failed with status: {response.status_code}"}

            mime = response.headers.get("Content-Type", "image/jpeg")
            return Response(content=response.content, media_type=mime)

        else:
            return {"error": f"Unrecognized art URL format: {url}"}

    except subprocess.CalledProcessError as e:
        print(f"{vars.player_type} command failed: {e}")
        return {"error": f"{vars.player_type} command failed: {e}"}
    except Exception as e:
        print(f"Unexpected error for {vars.player_type}: {e}")
        return {"error": f"Unexpected error for {vars.player_type}: {e}"}