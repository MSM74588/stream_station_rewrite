from app.players.mpdplayer import MPDPlayer
from app.players.spotifymprisplayer import SpotifyMPRISPlayer
from app.players.mpvplayer import MPVMediaPlayer
import re
from app.utils.spotify_auth_utils import is_spotify_setup, load_spotify_auth
from app.utils.ytdlp_helpers import get_media_data, extract_youtube_id
from fastapi import HTTPException
from app.variables import media_info
import app.variables as vars
from app.constants import SPOTIFY_MODE
from app.utils.history import log_history


async def handle_spotify_url(url: str, clean_player):
    
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
    print(f"🎧 Spotify Track ID: {track_id}")

    if SPOTIFY_MODE == "sp_client":
        clean_player(vars.player_instance)

        vars.player_instance = SpotifyMPRISPlayer(track_id)
        vars.player_type = vars.player_instance.type

        await log_history(vars.player_type, song_name=vars.player_instance.get_state().media_name) # type: ignore
        return vars.player_instance.get_state()
    else:
        raise HTTPException(status_code=501, detail="Spotify mode not implemented yet.")

async def handle_youtube_url(url: str, clean_player):
    
    try:
        data = get_media_data(url)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch media data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

    if data is None:
        raise HTTPException(status_code=404, detail="Media not found or unsupported format.")

    print(f"🎬 YouTube Data: {data}")

    media_info.title = data.get("title") # type: ignore
    media_info.upload_date = data.get("upload_date") # type: ignore
    media_info.uploader = data.get("uploader") # type: ignore
    media_info.channel = data.get("channel", data.get("channel_id")) # type: ignore
    media_info.url = data.get("webpage_url") # type: ignore
    media_info.video_id = extract_youtube_id(url)

    clean_player(vars.player_instance)

    vars.player_instance = MPVMediaPlayer(data.get("webpage_url")) # type: ignore
    vars.player_type = vars.player_instance.type

    await log_history(vars.player_type, song_name=vars.player_instance.get_state().get("media_name")) # type: ignore
    return vars.player_instance.get_state()

async def handle_mpd_song(song_name: str, clean_player):

    print(f"🎵 MPD Song Name: '{song_name}'")

    try:
        clean_player(vars.player_instance)
        vars.player_instance = MPDPlayer(song_name=song_name)
        vars.player_type = vars.player_instance.type

        await log_history(vars.player_type, song_name=vars.player_instance.get_state().media_name) # type: ignore

        vars.player_instance.play()

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    vars.player_info = vars.player_instance.get_state()
    if vars.player_info.status != "playing": # type: ignore
        raise HTTPException(status_code=404, detail=f"Song not found in MPD library: '{song_name}'")

    return vars.player_info
