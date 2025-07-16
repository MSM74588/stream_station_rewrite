from fastapi import APIRouter
from ..constants import CONTROL_MODE, IGNORE_PLAYERS
from ..variables import player_info, player_type, player_instance
from fastapi import FastAPI, Body, Query, Request

from ..variables import player_instance
from ..models import PlayerInfo, MediaData

from typing import Optional
from fastapi.exceptions import HTTPException

from ..players.mpdplayer import MPDPlayer

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
    
    # if it contains song_name then route to MPD playback, for local playback only. 
    if MediaData.song_name and not MediaData.url:
        song_name = MediaData.song_name.strip()
        print(f"🎵 MPD Song Name: '{song_name}'")
        # NOW HANDLE PLAYING MPD SONG
        
        # player_instance = MPDPlayer
        
        player_type = "mpd"
        
        try:
            player_instance = MPDPlayer(song_name=song_name)
            player_instance.play()
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))
        player_info = player_instance.get_state()
        
        # WHY this way? bcoz when running the subprocess command, it returns blank.
        # if player_info.status != "playing":
        #      raise HTTPException(status_code=404, detail=f"Song not found in MPD library: '{song_name}'")
        # else:
        #     print(f"🎵 Playing song: {player_info.media_name} by {player_info.media_uploader}")
        #     return player_info
        
        return player_info
    
    
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
        if player_instance.type == "mpd":
            # SET MPD REPEAT MODE
            player_instance.set_repeat()
            return {"status": "replaying", "player_status": "playing"}
        
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
        
    if player_instance.type == "mpd":
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