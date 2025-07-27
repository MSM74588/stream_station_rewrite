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
from app.utils.player_utils import wait_until_finished
import asyncio



import app.routers.player as playerRouter

import app.queue as queue

# Queue specific variables:
play_from_queue: bool = True

# async def play_next_in_queue():
#     if not queue.queue:
#         print("Queue is empty")
#     else:
#         if vars.player_instance is not None:
#             try:
#                 vars.player_instance.stop()
#                 vars.player_instance.unload()
#                 vars.player_instance = None
#             except Exception as e:
#                 raise ValueError(f"Failed to execute stop: {str(e)}")

        
#         popped_item = queue.queue.popleft()
        
#         if play_from_queue:
#             if popped_item.source == "mpd":
#                 await handle_mpd_song(popped_item.media_name, playerRouter.clean_player)
#             if popped_item.source == "youtube":
#                 await handle_youtube_url(popped_item.url, playerRouter.clean_player)
#             if popped_item.source == "spotify":
#                 await handle_spotify_next_song_played(popped_item.url)

async def play_next_in_queue():
    if not queue.queue:
        print("Queue is empty")
        return
    
    # Clean up current player more safely
    if vars.player_instance is not None:
        try:
            # Check if the player is still running before trying to stop it
            if hasattr(vars.player_instance, 'is_running') and vars.player_instance.is_running():
                print("🛑 Stopping current player...")
                await vars.player_instance.stop()
            else:
                print("🛑 Player already stopped, skipping stop command")
            
            # Always try to unload/cleanup

            if hasattr(vars.player_instance, 'cleanup'):
                await vars.player_instance.cleanup()
                
        except Exception as e:
            print(f"⚠️ Error while cleaning up player (continuing anyway): {str(e)}")
        finally:
            # Always reset the player instance
            vars.player_instance = None
            
    # Give the system time to clean up resources
    await asyncio.sleep(0.5)
    
    # Get next item from queue
    popped_item = queue.queue.popleft()
    
    if play_from_queue:
        try:
            if popped_item.source == "mpd":
                await handle_mpd_song(popped_item.media_name, playerRouter.clean_player)
            elif popped_item.source == "youtube":
                await handle_youtube_url(popped_item.url, playerRouter.clean_player)
            elif popped_item.source == "spotify":
                await handle_spotify_next_song_played(popped_item.url)
            else:
                print(f"⚠️ Unknown source: {popped_item.source}")
        except Exception as e:
            print(f"❌ Failed to start next player: {str(e)}")
            # Optionally, you could try the next item in queue here
            # or add the failed item back to the queue


def run_async_callback(callback):
    if asyncio.iscoroutinefunction(callback):
        asyncio.create_task(callback())
    else:
        callback()


# SPOTIFY SPECIFIC HANDLING.
is_spotify_autoplay: bool = False


async def handle_spotify_next_song_played(url):
    if not is_spotify_autoplay:
        if vars.player_instance is not None:
            try:
                await vars.player_instance.stop()
                await vars.player_instance.unload()
                vars.player_instance = None
            except Exception as e:
                raise ValueError(f"Failed to execute stop: {str(e)}")
    else:
        await handle_spotify_url(url, playerRouter.clean_player)
    
    

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
        await clean_player(vars.player_instance)
        
        # SETS UP PLAYER
        vars.player_instance = SpotifyMPRISPlayer(track_id)
        vars.player_type = vars.player_instance.type
        
        state = await vars.player_instance.get_state()
        

        # LOGS HISTORY
        await log_history(vars.player_type, song_name=state.media_name) # type: ignore
        # WAITS UNTIL FINISHED, THEN TRIGGERS THE FUCNTION PASSED (Callback)
        
        # THIS IS BAD DESIGN, since it listens for the song change indefinitely until changed, the server cant exit until the loop breaks i.e. condition met.
        # await wait_until_finished(vars.player_instance.type, vars.player_instance.get_state().media_name, on_finish=play_next_in_queue)
        # SO FOLLOW THIS WAY:
        asyncio.create_task(
            wait_until_finished(vars.player_instance.type, state.media_name, on_finish=lambda: run_async_callback(play_next_in_queue))
            )
        
        return await vars.player_instance.get_state()
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

    # print(f"🎬 YouTube Data: {data}")

    media_info.title = data.get("title") # type: ignore
    media_info.upload_date = data.get("upload_date") # type: ignore
    media_info.uploader = data.get("uploader") # type: ignore
    media_info.channel = data.get("channel", data.get("channel_id")) # type: ignore
    media_info.url = data.get("webpage_url") # type: ignore
    media_info.video_id = extract_youtube_id(url)

    await clean_player(vars.player_instance)

    vars.player_instance = MPVMediaPlayer(data.get("webpage_url")) # type: ignore
    
    # NOTE: Player needs to be started before fetching any kind of state
    await vars.player_instance.start()
    
    vars.player_type = vars.player_instance.type
    
    state = await vars.player_instance.get_state()

    await log_history(vars.player_type, song_name=state.media_name) # type: ignore
    asyncio.create_task(
            wait_until_finished(vars.player_instance.type, state.media_name), on_finish=lambda: run_async_callback(play_next_in_queue)
            )
    
    return await vars.player_instance.get_state()

async def handle_mpd_song(song_name: str, clean_player):

    print(f"🎵 MPD Song Name: '{song_name}'")

    try:
        await clean_player(vars.player_instance)
        vars.player_instance = MPDPlayer(song_name=song_name)
        vars.player_type = vars.player_instance.type
        
        await vars.player_instance.play()
        
        state = await vars.player_instance.get_state()
        

        await log_history(vars.player_type, song_name=state.media_name) # type: ignore
        asyncio.create_task(
            wait_until_finished(vars.player_instance.type, state.media_name, on_finish=lambda: run_async_callback(play_next_in_queue))
            )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    vars.player_info = await vars.player_instance.get_state()
    if vars.player_info.status != "playing": # type: ignore
        raise HTTPException(status_code=404, detail=f"Song not found in MPD library: '{song_name}'")

    return vars.player_info
