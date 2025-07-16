from fastapi import APIRouter
from ..constants import CONTROL_MODE, IGNORE_PLAYERS, SPOTIFY_MODE
from ..variables import player_info, player_type, player_instance
from fastapi import FastAPI, Body, Query, Request

from ..variables import player_instance
from ..models import PlayerInfo, MediaData

from typing import Optional
from fastapi.exceptions import HTTPException

from ..players.mpdplayer import MPDPlayer
from ..players.spotifymprisplayer import SpotifyMPRISPlayer

from ..utils.spotify_auth_utils import is_spotify_setup, load_spotify_auth
import re



# NAME IT WHATEVER YOU WANT, PLAYER_ROUTER IS JUST A SUGGESTION
router = APIRouter()


@router.get("/player", tags=["Player"], summary="Get Player Status", response_model=PlayerInfo)
def player_status():
    """
    Get the current status of the media player.
    """
    
    global player_instance
    
    
    # if CONTROL_MODE == "mpris":
        
    #     player_info = get_playerctl_data(player=player_type)
    #     return player_info
    # else:
    
    # REFACTOR THIS TO USE MPRIS CONTROLLER PLAYER
        
    if player_instance is not None:
        player_info.volume = int(player_instance.get_volume())
        player_info.media_progress = int(player_instance.get_progress())
        
    
        return player_info
    
@router.post("/player/play")
def play_media(MediaData: Optional[MediaData] = Body(None)):
    """
    Play media in the player.
    """
    
    global player_instance, player_type
    
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
            player_instance = SpotifyMPRISPlayer(track_id)
            player_info = player_instance.get_state()
            return player_info
        else:
            # TODO: Implement Spotify playback with 
            pass
    
    
@router.post("/player/stop")
def stop_player():
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
    

@router.post("/player/pause")
def pause_player():
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
    
    
@router.post("/player/replay")
def replay_player():
    if player_instance is not None:
        
            # SET MPD REPEAT MODE
        return {
            "replay enabled": player_instance.set_repeat(),
        }

        
        # TODO, FOR OTHER PLAYERS.
        
    else:
        raise HTTPException(status_code=400, detail="No media is currently loaded")
    
@router.post("/player/volume")
def set_volume(set: int = Query(..., ge=0, le=150, description="Volume percent (0-150)")):
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
@router.post("/player/next")
def player_next():
    return {"message": "TODO: player next"}
    
@router.post("/player/previous")
def player_previous():
    return {"message": "TODO: player prev"}