from fastapi import APIRouter
from ..constants import CONTROL_MODE, IGNORE_PLAYERS, SPOTIFY_MODE
from ..variables import player_info, player_type, player_instance
from fastapi import FastAPI, Body, Query, Request

from ..variables import player_instance, media_info
from ..models import PlayerInfo, MediaData

from typing import Optional
from fastapi.exceptions import HTTPException

from ..players.mpdplayer import MPDPlayer
from ..players.spotifymprisplayer import SpotifyMPRISPlayer
from ..players.mpvplayer import MPVMediaPlayer

from ..utils.spotify_auth_utils import is_spotify_setup, load_spotify_auth
import re

from ..utils.ytdlp_helpers import get_media_data, extract_youtube_id
from ..utils.player_utils import get_playerctl_data

# NAME IT WHATEVER YOU WANT, PLAYER_ROUTER IS JUST A SUGGESTION
router = APIRouter()

import subprocess
from pathlib import Path
from urllib.parse import urlparse, unquote
from fastapi.responses import Response
import requests

"""
TODO: Queue
- This has to be handled as per the link (if playlist link) provided, like if spotify is instructed to play a Playlist,
It should not initiate the queue, and the next and previous action should be directly be passed to mpris player to play the next song in the play list.
"""


@router.get("/", tags=["Player"], summary="Get Player Status", response_model=PlayerInfo)
def player_status():
    """
    # Player Status
    Gets the current status of the media player -> `player_instance`.
    """
    
    global player_instance
        
    if player_instance is not None:
        player_info = player_instance.get_state()
        return player_info
    
@router.post("/play", tags=["Player"])
def play_media(MediaData: Optional[MediaData] = Body(None)):
    """
    # Play Media
    if `player_instance` is not `None` i.e,  a player is loaded, then it triggers `play` action of player regardless if its paused
    or not.

    else, if `player_instance` is `None`, i.e no player loaded, then it takes either an `url` or `song_name`.
    It first processes `song_name` and if `song_name` is there, then it will play `MPD`
    
    if `url` is provided then:
    1. <b>spotify</b> will be played by `SpotifyMPRISPlayer`
    2. <b>Youtube</b> will be played by `MPVMediaPlayer`
    3. Then if any `unknown_url` is passed it will be handled via the `browser_url_handler` as per links mentioned in `url_handler.yaml` TODO
    4. Ultimately in case if no match, it will return an `HTTPException`
    """
    
    global player_instance, player_type
    
    def _clean_player(player):
        try:
            if player is not None:
                player.stop()
                del player
                player = None
        except:
            ValueError("Cannot Stop Player")
    
    # PLAIN PLAYBACK CONTROL, IF NOT DATA IS PASSED
    if player_instance is not None and not MediaData:
        # CAN BE MPRIS, MPD, MPV
        player_instance.play()
        
        
    # IF PLAYER_INSTANCE is Empty, then Check if the DATA is complete, to be played 
    if MediaData is None or (not MediaData.url and not MediaData.song_name):
        raise HTTPException(status_code=400, detail="Media URL or song name is required.")
    
    # MPD PLAYBACK -----------------------------------------------------------------
    
    # if it contains song_name then route to MPD playback, for local playback only. 
    if MediaData.song_name and not MediaData.url:
        song_name = MediaData.song_name.strip()
        print(f"🎵 MPD Song Name: '{song_name}'")
        # NOW HANDLE PLAYING MPD SONG
        try:
            _clean_player(player_instance)
            
            player_instance = MPDPlayer(song_name=song_name)
            player_type = player_instance.type
            player_instance.play()
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        player_info = player_instance.get_state()
        
        # WHY this way? bcoz when running the subprocess command, it returns blank.
        if player_info.status != "playing":
             raise HTTPException(status_code=404, detail=f"Song not found in MPD library: '{song_name}'")
        else:
            return player_info
        
    url = MediaData.url.strip() # type: ignore
        
    # SPOTIFY PLAYBACK -------------------------------------------------------------
    if "spotify.com" in url:
        if not is_spotify_setup():
            raise HTTPException(status_code=403, detail="Spotify is not authenticated. Please visit /setup.")
        try:
            sp = load_spotify_auth()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to authenticate with Spotify: {str(e)}")
        
        match = re.search(r"track/([A-Za-z0-9]+)", url)
        
        if not match:
            raise HTTPException(status_code=400, detail="Invalid Spotify track URL")
        
        track_id = match.group(1)
        print(f"SPOTIFY TRACK ID: {track_id}")
        
        if SPOTIFY_MODE == "sp_client":
            _clean_player(player_instance)
            
            player_instance = SpotifyMPRISPlayer(track_id)
            player_type = player_instance.type
            player_info = player_instance.get_state()
            return player_info
        else:
            # TODO: Implement Spotify playback with YTDLP
            pass
        
    elif "youtube.com" in url or "youtu.be" in url:
        try:
            data = get_media_data(url)
        except ValueError as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch media data: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
        
        if data is None:
            raise HTTPException(status_code=404, detail="Media not found or unsupported format.")
        
        print(f"Media Data: {data}")
        
        media_info.title=data.get("title")
        media_info.upload_date=data.get("upload_date")
        media_info.uploader=data.get("uploader")
        media_info.channel=data.get("channel", data.get("channel_id")) # fallback if channel is missing
        media_info.url=data.get("webpage_url")
        media_info.video_id=extract_youtube_id(url)  # Extract YouTube ID for reference
        
        _clean_player(player_instance)
        
        player_instance = MPVMediaPlayer(data.get("webpage_url"))
        player_type = player_instance.type
        
        
        return player_instance.get_state()
    
    else:
        raise HTTPException(status_code=400, detail="Unsupported media URL. Only Spotify and YouTube URLs are supported.")
        
    
        
    
    
    
@router.post("/stop", tags=["Player"])
def stop_player():
    """
    # Stops Player
    Stops Player and Unloads them from `player_instance`
    """
    global player_instance    
    if player_instance is None:
            raise HTTPException(status_code=400, detail="No media is currently loaded")
    try:
        player_instance.stop()
        player_instance = None  # Reset the player instance                
        # Reset the STATE
        player_info = PlayerInfo()
        player_info.status = "stopped"
        return player_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute stop: {str(e)}")
    

@router.post("/pause", tags=["Player"])
def pause_player():
    """
    # Pause the current player
    """
    global player_instance
    global player_info
    if player_instance is None:
        raise HTTPException(status_code=400, detail="No media is currently loaded")
    
    try:
        player_instance.pause()
        player_info = player_instance.get_state()
        # player_info. = PlayerInfo(is_paused=True)
        
        return player_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to execute pause: {str(e)}")
    
    
@router.post("/loop", tags=["Player"])
def loop_player():
    """
    # Set Loop Mode of Player
    Toggles the loop mode for the player, it only sets track loop mode, i.e single loop for ALL types of players.
    """
    if player_instance is not None:
        
            # SET MPD REPEAT MODE
        return {
            "loop enabled": player_instance.set_repeat(),
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
    global player_info
    global player_type
    
    if player_instance is None:
        raise HTTPException(status_code=400, detail="No media is currently loaded")
    
    if not (0 <= set <= 150):
            raise HTTPException(status_code=400, detail="Volume must be between 0 and 150")
        
    if player_instance.type == "mpd" or player_instance.type == "spotify":
        # Cap set to 100 for mpd
        set = min(set, 100)
        
    player_instance.set_volume(set)
                
    player_info = player_instance.get_state()
    return player_info


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
    If no player is running, i.e `player_instance` is `None`, returns an HTTPException
    """
    global player_type

    valid_states_by_player = {
        "spotify": ["playing", "paused"],
        "mpd": ["playing"],
        "mpv": ["playing", "paused"]  # if supported via playerctl
    }

    valid_states = valid_states_by_player.get(player_type, [])

    try:
        status = subprocess.check_output(
            ["playerctl", "--player=" + player_type, "status"],
            text=True
        ).strip().lower()
        print(f"{player_type} status: {status}")

        if status not in valid_states:
            return {"error": f"{player_type} not in a valid state"}

        url = subprocess.check_output(
            ["playerctl", "--player=" + player_type, "metadata", "mpris:artUrl"],
            text=True
        ).strip()
        print(f"{player_type} artUrl: {url}")

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
        print(f"{player_type} command failed: {e}")
        return {"error": f"{player_type} command failed: {e}"}
    except Exception as e:
        print(f"Unexpected error for {player_type}: {e}")
        return {"error": f"Unexpected error for {player_type}: {e}"}