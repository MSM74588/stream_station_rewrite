from sqlmodel import SQLModel, Field
from typing import Optional
import uuid
from datetime import datetime, timezone


class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = None
    
class SpotifyLikedSongItem(SQLModel, table=True):
    id: str = Field(default=None, primary_key=True)
    name: str
    artist: str
    album_art: Optional[str]
    spotify_url: str
    
class FavouritedSongs(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    song_name: str
    artist: str
    url: str
    date_added: Optional[str]
    type: str
    cover_art_url: Optional[str]
    

    
class Podcast(SQLModel, table=True):
    id: str = Field(primary_key=True)
    source: str
    title: str
    url: str
    channel: str
    
class Episode(SQLModel, table=True):
    id: str = Field(primary_key=True)
    url: str
    thumbnail_url: str
    uploader: str
    upload_date: str
    
    
class History(SQLModel, table=True):
    time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), primary_key=True)
    song_name: str
    duration: int
    url: int
    player_type: str

# DATA MODELS ------------------------------------------------------- #
from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List


class SongMetadataModel(BaseModel):
    media_name: str
    artist: Optional[str]
    album: Optional[str]
    duration: Optional[int]  # in seconds
    source: Optional[str]
    url: Optional[str]
    
class QueueItem(BaseModel):
    url: Optional[str] = None
    file_name: Optional[str] = None
    song_name: Optional[str] = None

class PlayerInfo(BaseModel):
    status: Optional[str] = None
    current_media_type: Optional[str] = None
    volume: Optional[int] = 0
    is_paused: bool = False
    cache_size: int = 0
    media_name: Optional[str] = ""
    media_uploader: Optional[Any] = ""
    media_duration: int = 0  # string default as "0"
    media_progress: int = 0
    is_live: Optional[bool] = False
    media_url: Optional[str] = ""
    

class MediaData(BaseModel):
    url: Optional[str] = Field(
        None, 
        description="The URL of the media to play. Supported sources: YouTube, Spotify."
    )
    song_name: Optional[str] = Field(
        None, 
        description="Name of the song to search and play from MPD if URL is not provided."
    )
    file_path: Optional[str] = Field(
        None,
        description="Absolute or relative file path to the media file to play using MPD."
    )
    
class MediaInfo(BaseModel):
    title: Optional[str] = ""
    upload_date: Optional[str] = ""
    uploader: Optional[str] = ""
    channel: Optional[str] = ""
    url: Optional[str] = ""
    video_id: Optional[str] = ""
    
class LastPlayedMedia(BaseModel):
    title: str
    url: str