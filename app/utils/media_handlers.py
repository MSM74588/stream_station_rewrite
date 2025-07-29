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

from typing import Optional

import app.routers.player as playerRouter
import app.queue as queue

# Add these at the top of your file
_queue_lock = asyncio.Lock()
_current_monitoring_task: Optional[asyncio.Task] = None
_is_processing_queue = False


# Queue specific variables:
play_from_queue: bool = True

async def play_next_in_queue():
    global _queue_lock, _current_monitoring_task, _is_processing_queue
    
    # Prevent concurrent queue processing
    async with _queue_lock:
        if _is_processing_queue:
            print("⚠️ Queue processing already in progress, skipping...")
            return
            
        _is_processing_queue = True
        
        try:
            # Use a while loop instead of recursion to avoid deadlocks
            while queue.queue:
                print("🔄 Playing next song from queue...")
                
                # Cancel any existing monitoring task
                if _current_monitoring_task and not _current_monitoring_task.done():
                    print("🛑 Cancelling previous monitoring task...")
                    _current_monitoring_task.cancel()
                    try:
                        await _current_monitoring_task
                    except asyncio.CancelledError:
                        pass
                    _current_monitoring_task = None
                
                # Clean up current player
                if vars.player_instance is not None:
                    try:
                        print("🛑 Stopping current player...")
                        
                        if hasattr(vars.player_instance, 'stop'):
                            if asyncio.iscoroutinefunction(vars.player_instance.stop):
                                await vars.player_instance.stop()
                            else:
                                vars.player_instance.stop()
                        
                        if hasattr(vars.player_instance, 'unload'):
                            if asyncio.iscoroutinefunction(vars.player_instance.unload):
                                await vars.player_instance.unload()
                            else:
                                vars.player_instance.unload()
                                
                    except Exception as e:
                        print(f"⚠️ Error while cleaning up player (continuing anyway): {str(e)}")
                    finally:
                        vars.player_instance = None
                        vars.player_type = ""
                        
                # Give the system time to clean up resources
                await asyncio.sleep(1.0)
                
                # Get next item from queue
                try:
                    popped_item = queue.queue.popleft()
                    print(f"🎵 Next song: {popped_item.media_name if hasattr(popped_item, 'media_name') else 'Unknown'}")
                except IndexError:
                    print("⚠️ Queue became empty during processing")
                    break
                
                if not play_from_queue:
                    break
                    
                try:
                    # Define a dummy clean function for compatibility
                    async def dummy_clean_player(player):
                        pass
                        
                    if popped_item.source == "mpd":
                        result = await handle_mpd_song(popped_item.media_name, dummy_clean_player)
                        if result is not None:
                            # Successfully started MPD, exit the while loop
                            break
                        else:
                            print("🔄 MPD failed, trying next song...")
                            await asyncio.sleep(0.5)
                            # Continue the while loop to try next song
                            continue
                            
                    elif popped_item.source == "youtube":
                        await handle_youtube_url(popped_item.url, dummy_clean_player)
                        # Successfully started YouTube, exit the while loop
                        break
                        
                    elif popped_item.source == "spotify":
                        await handle_spotify_next_song_played(popped_item.url)
                        # Successfully started Spotify, exit the while loop
                        break
                        
                    else:
                        print(f"⚠️ Unknown source: {popped_item.source}")
                        await asyncio.sleep(0.5)
                        # Continue the while loop to try next song
                        continue
                        
                except Exception as e:
                    print(f"❌ Failed to start player: {str(e)}")
                    await asyncio.sleep(0.5)
                    # Continue the while loop to try next song
                    continue
            
            if not queue.queue:
                print("🎵 Queue is now empty")
                        
        finally:
            _is_processing_queue = False



async def start_song_monitoring(song_name: str, player_type: str):
    """Start monitoring the current song and handle queue advancement"""
    global _current_monitoring_task
    
    try:
        print(f"⏳ Starting to monitor: {song_name}")
        
        # Properly await the monitoring
        await wait_until_finished(
            player_type=player_type,
            song_name=song_name,
            check_interval=2
        )
        
        print("✅ Song completed, advancing queue...")
        await play_next_in_queue()
        
    except asyncio.CancelledError:
        print("🔄 Song monitoring was cancelled")
        # Don't call play_next_in_queue() when cancelled
        raise
    except Exception as e:
        print(f"⚠️ Error monitoring song: {e}")
        # Attempt to advance queue on error
        if queue.queue:
            print("🔄 Attempting to advance queue due to monitoring error...")
            await play_next_in_queue()


# SPOTIFY SPECIFIC HANDLING.
is_spotify_autoplay: bool = False

# FIXME

async def handle_spotify_next_song_played(url):
    if not is_spotify_autoplay:
        if vars.player_instance is not None:
            try:
                if hasattr(vars.player_instance, 'stop'):
                    if asyncio.iscoroutinefunction(vars.player_instance.stop):
                        await vars.player_instance.stop()
                    else:
                        vars.player_instance.stop()
                
                if hasattr(vars.player_instance, 'unload'):
                    if asyncio.iscoroutinefunction(vars.player_instance.unload):
                        await vars.player_instance.unload()
                    else:
                        vars.player_instance.unload()
                        
                vars.player_instance = None
                vars.player_type = ""
            except Exception as e:
                raise ValueError(f"Failed to execute stop: {str(e)}")
        
        # ✅ ADD THIS: Actually open Spotify!
        print(f"🎧 Opening Spotify URL: {url}")
        try:
            # FIXME Wait until finished function to be ran.
            await handle_spotify_url(url=url, clean_player=playerRouter.clean_player)
            print("✅ Spotify opened successfully")
        except Exception as e:
            print(f"❌ Failed to open Spotify: {e}")
            
    else:
        await handle_spotify_url(url, playerRouter.clean_player)

async def handle_spotify_url(url: str, clean_player):
    global _current_monitoring_task
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
        print("SPOTIFY SP_CLIENT MODE")
        
        await clean_player(vars.player_instance)
        
        # SETS UP PLAYER
        # FIXME
        print("setting up mpris player")
        vars.player_instance = SpotifyMPRISPlayer(track_id)
        print(vars.player_instance)
        
        # FIXME, why is this needed?
        a = await vars.player_instance.async_init()
        
        vars.player_type = vars.player_instance.type
        
        state = await vars.player_instance.get_state()

        # LOGS HISTORY
        print("HISTORY LOGGING??")
        await log_history(vars.player_type, song_name=state.media_name)
        
        # FIXED: Proper task creation for monitoring
        _current_monitoring_task = asyncio.create_task(
            start_song_monitoring(state.media_name, vars.player_type)
        )
        
        return await vars.player_instance.get_state()
    else:
        raise HTTPException(status_code=501, detail="Spotify mode not implemented yet.")

async def handle_youtube_url(url: str, clean_player):
    global _current_monitoring_task
    try:
        data = get_media_data(url)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch media data: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

    if data is None:
        raise HTTPException(status_code=404, detail="Media not found or unsupported format.")

    # Set media info
    media_info.title = data.get("title")
    media_info.upload_date = data.get("upload_date")
    media_info.uploader = data.get("uploader")
    media_info.channel = data.get("channel", data.get("channel_id"))
    media_info.url = data.get("webpage_url")
    media_info.video_id = extract_youtube_id(url)

    await clean_player(vars.player_instance)

    # Create and start MPV player
    vars.player_instance = MPVMediaPlayer(data.get("webpage_url"))
    
    # Store media info in player for later access
    vars.player_instance.info = {
        "title": data.get("title", "Unknown"),
        "uploader": data.get("uploader", "Unknown"),
        "channel": data.get("channel", data.get("channel_id", "Unknown")),
        "webpage_url": data.get("webpage_url", url),
        "duration": data.get("duration", 0),
        "is_live": data.get("is_live", False)
    }
    
    # NOTE: Player needs to be started before fetching any kind of state
    await vars.player_instance.start()
    vars.player_type = vars.player_instance.type
    
    state = await vars.player_instance.get_state()

    # Log history
    await log_history(vars.player_type, song_name=state.media_name)
    
    # FIXED: Proper task creation for monitoring
    _current_monitoring_task = asyncio.create_task(
        start_song_monitoring(state.media_name, vars.player_type)
    )
    
    return await vars.player_instance.get_state()

async def handle_mpd_song(song_name: str, clean_player):
    global _current_monitoring_task
    
    print(f"🎵 MPD Song Name: '{song_name}'")

    try:
        await clean_player(vars.player_instance)
        vars.player_instance = MPDPlayer(song_name=song_name)
        vars.player_type = vars.player_instance.type
        
        print("PLAYING MPD PLAYER??????/")
        await vars.player_instance.start()
        await vars.player_instance.play()
        
        # Give MPD more time to start playing
        await asyncio.sleep(1.0)
        
        state = await vars.player_instance.get_state()

        # Check if the song is actually playing or at least loaded
        if state.status not in ["playing", "paused"] or not state.media_name:
            print(f"⚠️ Song '{song_name}' not found in MPD library or failed to start")
            
            # Clean up the failed player
            if vars.player_instance:
                try:
                    if hasattr(vars.player_instance, 'stop'):
                        if asyncio.iscoroutinefunction(vars.player_instance.stop):
                            await vars.player_instance.stop()
                        else:
                            vars.player_instance.stop()
                    
                    if hasattr(vars.player_instance, 'unload'):
                        if asyncio.iscoroutinefunction(vars.player_instance.unload):
                            await vars.player_instance.unload()
                        else:
                            vars.player_instance.unload()
                except Exception as cleanup_error:
                    print(f"⚠️ Error cleaning up failed MPD player: {cleanup_error}")
                finally:
                    vars.player_instance = None
                    vars.player_type = ""
            
            # Return None to indicate failure (don't start monitoring)
            return None

        # Log history only if song is successfully playing
        await log_history(vars.player_type, song_name=state.media_name)
        
        # Start monitoring with proper task management
        _current_monitoring_task = asyncio.create_task(
            start_song_monitoring(state.media_name, vars.player_type)
        )

        vars.player_info = state
        return vars.player_info

    except ValueError as e:
        print(f"⚠️ MPD ValueError: {str(e)}")
        # Clean up on error
        if vars.player_instance:
            try:
                if hasattr(vars.player_instance, 'unload'):
                    if asyncio.iscoroutinefunction(vars.player_instance.unload):
                        await vars.player_instance.unload()
                    else:
                        vars.player_instance.unload()
            except:
                pass
            finally:
                vars.player_instance = None
                vars.player_type = ""
        return None
        
    except Exception as e:
        print(f"❌ Unexpected MPD error: {str(e)}")
        # Clean up on error
        if vars.player_instance:
            try:
                if hasattr(vars.player_instance, 'unload'):
                    if asyncio.iscoroutinefunction(vars.player_instance.unload):
                        await vars.player_instance.unload()
                    else:
                        vars.player_instance.unload()
            except:
                pass
            finally:
                vars.player_instance = None
                vars.player_type = ""
        return None

