from .spotify_auth_utils import load_spotify_auth
from sqlmodel import Session, select
from app.models import SpotifyLikedSongItem
from app.database import engine

def get_all_liked_songs_from_db():
    try:
        with Session(engine) as session:
            songs = session.exec(select(SpotifyLikedSongItem)).all()
            return [song.model_dump() for song in songs]
    except Exception as e:
        return e
    

def fetch_liked_songs_from_spotify():
    sp = load_spotify_auth()
    songs = []

    results = sp.current_user_saved_tracks(limit=50)

    with Session(engine) as session:
        while results:
            for item in results["items"]:
                track = item["track"]
                
                name = track.get("name") or "Unknown Title"
                artist = track["artists"][0]["name"] if track["artists"] else "Unknown Artist"
                album_art = track["album"]["images"][0]["url"] if track["album"]["images"] else None
                
                if not album_art:
                    album_art = "https://example.com/default.jpg"  # fallback image
                
                song_data = {
                    "id": track["id"],
                    "name": track["name"],
                    "artist": track["artists"][0]["name"],
                    "album_art": track["album"]["images"][0]["url"] if track["album"]["images"] else None,
                    "spotify_url": track["external_urls"]["spotify"]
                }

                # Check if this song is already in the DB
                existing = session.exec(
                    select(SpotifyLikedSongItem).where(SpotifyLikedSongItem.id == song_data["id"])
                ).first()
                
                if not existing:
                    song = SpotifyLikedSongItem(**song_data)
                    session.add(song)
                    songs.append(song)
                else:
                    # Ensure it's a full dict version of the existing object
                    songs.append(existing.model_dump())

            session.commit()

            if results["next"]:
                results = sp.next(results)
            else:
                break
    return songs
