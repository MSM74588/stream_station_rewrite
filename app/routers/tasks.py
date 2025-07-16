from fastapi import APIRouter, HTTPException

router = APIRouter()

@app.get("/songs/spotify")
def get_spotify_songs():
    """
    Fetch liked songs from spotify, sync them to DB and the reurn the songs.
    if sync parameter is passed, then it will freshly fetch the songs from Spotify.
    else, it will return the songs from the local database.
    """

    # If DB is empty, fetch from Spotify and save
    songs = get_songs_from_db()
    if not songs:
        try:
            songs = fetch_liked_songs_from_spotify()
            save_songs_to_db(songs)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to fetch from Spotify: {e}")
    return songs
    # Modify this to accept a parameter to manually sync when needed