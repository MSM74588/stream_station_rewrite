from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session
from app.database import get_session
from app.models import Podcast, Episode
import uuid
from typing import Optional
from pydantic import BaseModel
import re
import subprocess
import json
from typing import List, Optional
from pydantic import BaseModel, HttpUrl
from urllib.parse import urlparse
import feedparser
import requests


from app.utils.spotify_auth_utils import is_spotify_setup, load_spotify_auth
sp = load_spotify_auth()

class PodcastParamsBody(BaseModel):
    url: Optional[str]

class PodcastItem(BaseModel):
    title: str
    url: HttpUrl
    thumbnail: Optional[HttpUrl] = None
    uploader: Optional[str] = None
    upload_date: Optional[str] = None  # UTC ISO string

class PodcastSource(BaseModel):
    type: str
    url: HttpUrl
    title: Optional[str] = None
    channel: Optional[str] = None
    items: List[PodcastItem]

router = APIRouter()

# --- Handler registry ---
async def handle_youtube_playlist(url: str) -> PodcastSource:
    try:
        result = subprocess.run(
            ["yt-dlp", "-J", url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20
        )

        if result.returncode != 0:
            raise Exception(result.stderr.strip())

        data = json.loads(result.stdout)
        entries = data.get("entries", [])

        items = []
        for entry in entries:
            if not entry or "id" not in entry:
                continue

            video_url = f"https://www.youtube.com/watch?v={entry['id']}"
            upload_date = entry.get("upload_date")
            iso_date = None
            if upload_date:
                iso_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}T00:00:00Z"

            items.append(PodcastItem(
                title=entry.get("title"),
                url=video_url,
                thumbnail=entry.get("thumbnail"),
                uploader=entry.get("uploader"),
                upload_date=iso_date
            ))

        return PodcastSource(
            type="YouTube Playlist",
            url=url,
            title=data.get("title"),
            channel=data.get("uploader"),
            items=items
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch playlist: {str(e)}")



async def handle_youtube_channel(url: str) -> PodcastSource:
    try:
        result = subprocess.run(
            ["yt-dlp", "-J", url],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=20
        )

        if result.returncode != 0:
            raise Exception(result.stderr.strip())

        data = json.loads(result.stdout)
        entries = data.get("entries", [])

        items = []
        for entry in entries:
            if not entry or "id" not in entry:
                continue

            video_url = f"https://www.youtube.com/watch?v={entry['id']}"
            upload_date = entry.get("upload_date")
            iso_date = None
            if upload_date:
                iso_date = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}T00:00:00Z"

            items.append(PodcastItem(
                title=entry.get("title"),
                url=video_url,
                thumbnail=entry.get("thumbnail"),
                uploader=entry.get("uploader"),
                upload_date=iso_date
            ))

        return PodcastSource(
            type="YouTube Channel",
            url=url,
            title=data.get("title"),
            channel=data.get("uploader"),
            items=items
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch channel: {str(e)}")

def extract_show_id(url: str) -> str:
    path = urlparse(url).path
    return path.split('/')[-1]

async def handle_spotify_show(url: str) -> PodcastSource:
    try:
        show_id = extract_show_id(url)
        show = sp.show(show_id)
        episodes_data = sp.show_episodes(show_id, limit=50)

        items = []
        for ep in episodes_data["items"]:
            items.append(PodcastItem(
                title=ep["name"],
                url=ep["external_urls"]["spotify"],
                thumbnail=ep["images"][0]["url"] if ep["images"] else None,
                uploader=show["publisher"],
                upload_date=f"{ep['release_date']}T00:00:00Z" if ep.get("release_date") else None
            ))

        return PodcastSource(
            type="Spotify Show",
            url=url,
            title=show["name"],
            channel=show["publisher"],
            items=items
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch Spotify show: {str(e)}")


async def handle_rss_feed(url: str) -> PodcastSource:
    try:
        # Fetch and parse RSS feed
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            raise Exception(f"Status code: {response.status_code}")
        
        feed = feedparser.parse(response.content)
        if not feed.entries:
            raise Exception("No entries found in RSS feed")

        items = []
        for entry in feed.entries:
            audio_url = None
            if 'enclosures' in entry and entry.enclosures:
                audio_url = entry.enclosures[0].get('href')

            if not audio_url:
                continue  # Skip if no playable media

            upload_date = None
            if entry.get("published_parsed"):
                from datetime import datetime
                upload_date = datetime(*entry.published_parsed[:6]).isoformat() + "Z"

            thumbnail = None
            if "itunes_image" in entry:
                thumbnail = entry.itunes_image.get("href")
            elif "image" in entry:
                thumbnail = entry.image.get("href")
            elif "media_thumbnail" in entry:
                thumbnail = entry.media_thumbnail[0].get("url")

            uploader = (
                entry.get("itunes_author") or
                entry.get("author") or
                entry.get("dc_creator")
            )

            items.append(PodcastItem(
                title=entry.get("title", "Untitled"),
                url=audio_url,
                thumbnail=thumbnail,
                uploader=uploader,
                upload_date=upload_date
            ))

        return PodcastSource(
            type="RSS Feed",
            url=url,
            title=feed.feed.get("title"),
            channel=feed.feed.get("itunes_author") or feed.feed.get("author"),
            items=items
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch RSS feed: {str(e)}")

# --- Matcher definitions ---
def is_youtube_playlist(url: str) -> bool:
    return "youtube.com/playlist" in url or "list=" in url

def is_youtube_channel(url: str) -> bool:
    return re.search(r"(youtube\.com/(c/|@|channel/))", url) is not None

def is_spotify_show(url: str) -> bool:
    return "open.spotify.com/show/" in url

def is_rss_feed(url: str) -> bool:
    try:
        feed = feedparser.parse(url)
        return bool(feed.entries)
    except Exception:
        return False

def safe_get(url: str, timeout: float = 4.0) -> str:
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (PodcastFetcher/1.0)"
        }
        response = requests.get(url, timeout=timeout, headers=headers)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"[safe_get] Failed to fetch URL: {url} -> {e}")
        return ""

# --- Dispatcher ---
@router.get("/podcast", tags=["Podcasts"])
async def handle_get():
    return {
        "message" : "Please send a POST req with Body"
    }

@router.post("/podcast", tags=["Podcasts"])
async def handle_podcast(request: PodcastParamsBody):
    url = request.url.strip()

    handlers = [
        (is_youtube_playlist, handle_youtube_playlist),
        (is_youtube_channel, handle_youtube_channel),
        (is_spotify_show, handle_spotify_show),
        (is_rss_feed, handle_rss_feed),
    ]

    for matcher, handler in handlers:
        if matcher(url):
            return await handler(url)

    raise HTTPException(status_code=400, detail="Unsupported podcast URL type")

@router.get("/podcast/episodes",tags=["Podcasts"])
async def fetch_episodes():
    """
    # Fetch episodes of podcast
    """
    return {"episodes": "podcast episodes"}


@router.post("/podcast/save", tags=["Podcasts"])
async def save_podcast(body: PodcastParamsBody, session: Session = Depends(get_session)):
    url = body.url.strip()

    # Match handlers
    handlers = [
        (is_youtube_playlist, handle_youtube_playlist),
        (is_youtube_channel, handle_youtube_channel),
        (is_spotify_show, handle_spotify_show),
        (is_rss_feed, handle_rss_feed),
    ]

    for matcher, handler in handlers:
        if matcher(url):
            podcast: PodcastSource = await handler(url)

            db_podcast = Podcast(
                id=str(uuid.uuid4()),
                source=podcast.type,
                title=podcast.title,
                url=podcast.url,
                channel=podcast.channel or podcast.uploader or "Unknown"
            )

            session.add(db_podcast)
            session.commit()
            return {"status": "saved", "podcast_id": db_podcast.id}

    raise HTTPException(status_code=400, detail="Unsupported podcast URL type")

@router.post("/episode/save", tags=["Podcasts"])
async def save_episode(body: PodcastParamsBody, session: Session = Depends(get_session)):
    url = body.url.strip()

    # For episode, we can reuse the same detectors but aim to extract a single item
    # Assume handle_episode is a function that returns metadata for single item
    episode = await get_episode_metadata(url)

    if not episode:
        raise HTTPException(status_code=400, detail="Unsupported or unrecognized episode URL")

    # FIXME, I want to use the name of podcast as id.
    db_episode = Episode(
        id=str(uuid.uuid4()),
        url=episode.url,
        thumbnail_url=episode.thumbnail or "",
        uploader=episode.uploader or "Unknown",
        upload_date=episode.upload_date or ""
    )

    session.add(db_episode)
    session.commit()
    return {"status": "saved", "episode_id": db_episode.id}

# helper functions
import yt_dlp
from typing import Optional
from pydantic import BaseModel

class EpisodeMetadata(BaseModel):
    url: str
    title: str
    thumbnail: Optional[str]
    uploader: Optional[str]
    upload_date: Optional[str]

async def get_episode_metadata(url: str) -> Optional[EpisodeMetadata]:
    ydl_opts = {"quiet": True, "skip_download": True, "extract_flat": False, "force_generic_extractor": False, "dump_single_json": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return EpisodeMetadata(
                url=info.get("webpage_url"),
                title=info.get("title"),
                thumbnail=info.get("thumbnail"),
                uploader=info.get("uploader"),
                upload_date=info.get("upload_date")
            )
    except Exception as e:
        print(f"Failed to extract episode metadata: {e}")
        return None

# FIXME, Deduplication logic
