from fastapi import APIRouter, Body, File, UploadFile, Depends, HTTPException, Query
from uuid import uuid4
import os
from app.models import FavouritedSongs
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional
from app.constants import COVER_ART_PATH, COVER_ART_URL_PREFIX

from sqlmodel import Session, select

from app.database import engine


router = APIRouter()

@router.post("/favourites")
async def liked_songs_post(
    song_name: str = Body(..., embed=True),
    artist: str = Body("", embed=True),
    url: Optional[str] = Body(None, embed=True),
    image: UploadFile = File(None)
):
    """
    # Add Favourite songs
    The songs has to be added manually via this API endpoint.
    """
    # Determine type
    song_type: str = ""
    
    # TODO: Make it smart later. Auto FIlter to specific URL.
    
    if url:
        if "youtube.com" in url or "youtu.be" in url:
            song_type = "youtube"
        elif "spotify.com" in url:
            song_type = "spotify"
        else:
            song_type = "mpd"
    else:
        song_type = "mpd"
        url = ""

    # Handle image upload
    cover_art_url: str
    
    if image and image.filename:
        ext = os.path.splitext(image.filename or "")[-1]
        filename = f"{uuid4().hex}{ext}"
        file_path = COVER_ART_PATH / filename
        with open(file_path, "wb") as f:
            f.write(await image.read())
        cover_art_url = f"{COVER_ART_URL_PREFIX}/{filename}"

    # Save to DB (update your add_liked_song to accept artist and cover_art_url)
    # song = add_liked_song(song_name, url, song_type, artist, cover_art_url)
    
    try:
        with Session(engine) as session:
            # Check for existing URL
            if url:
                statement = select(FavouritedSongs).where(FavouritedSongs.url == url)
                existing_song = session.exec(statement).first()
                if existing_song:
                    raise HTTPException(
                        status_code=409,
                        detail="A song with the same URL already exists in the database."
                    )

            # Create and add song
            song = FavouritedSongs(
                song_name=song_name,
                artist=artist,
                url=url,
                type=song_type,
                date_added=datetime.now(timezone.utc).isoformat(),
                cover_art_url=cover_art_url
            )
            session.add(song)
            session.commit()
            session.refresh(song)
            return {"message": "Song added to liked songs.", "song": song}

    except HTTPException:
        raise  # Re-raise to keep the 409 error intact
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add song to DB: {e}")

@router.get("/favourites")
def get_all_favourited_songs(type: Optional[str] = Query(None, description="Filter by song type (e.g. youtube, spotify, mpd, ...)")):
    """
    # Get Favourite Songs
    Get the Manually Added Favourited Songs, can be filtered by add a `type=` parameter
    """
    try:
        with Session(engine) as session:
            if type:
                statement = select(FavouritedSongs).where(FavouritedSongs.type == type.lower())
            else:
                statement = select(FavouritedSongs)
            songs = session.exec(statement).all()
            return {"songs": songs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch songs: {e}")