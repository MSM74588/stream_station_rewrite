from fastapi import APIRouter, HTTPException, Query, Request
from app.models import SpotifyLikedSongItem
from typing import List
from ..utils.spotify_fetchers import fetch_liked_songs_from_spotify, get_all_liked_songs_from_db

router = APIRouter()

@router.get("/songs/spotify", response_model=List[SpotifyLikedSongItem])
def get_spotify_songs(request: Request):
    """
    Fetch liked songs from spotify, sync them to DB and the reurn the songs.
    if sync parameter is passed, then it will freshly fetch the songs from Spotify.
    else, it will return the songs from the local database.
    """
    
    sync_param = request.query_params.get("sync")
    
    # If sync param is present and NOT in the list of falsey values
    if sync_param is not None and sync_param.lower() not in ["false", "0", "no"]:
        try:
            songs = fetch_liked_songs_from_spotify()
            # save_songs_to_db(songs)
            return songs    
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch from Spotify: {e}")
    
    # If sync is absent or explicitly false
    return get_all_liked_songs_from_db()