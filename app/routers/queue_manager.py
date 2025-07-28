from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from app.utils.metadata_fetchers import get_youtube_metadata, get_mpd_by_metadata, get_spotify_info
from app.models import QueueItem
import app.queue as queue

from fastapi import Body
from pydantic import BaseModel, HttpUrl, Field




router = APIRouter()

# --- Models ---



def is_spotify_url(url: str) -> bool:
    return "open.spotify.com" in url and ("track/" in url or "episode/" in url)

def is_youtube_url(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url


# --- Placeholder Handlers ---

def add_raw_url(url: str):
    return {"source": "direct", "url": url}


@router.post("/queue/add")
def add_to_queue(items: List[QueueItem], background_tasks: BackgroundTasks):
    """
    # Add to queue
    Accepts List of items and schedules metadata fetching and queueing in the background.
    Immediately returns a success response.
    """
    if not items:
        raise HTTPException(status_code=400, detail="Empty list received")

    # Schedule background task
    background_tasks.add_task(process_and_add_to_queue, items)

    return {
        "message": "Items scheduled to be added to queue"
    }


@router.post("/queue/clear")
def clear_queue():
    """
    # Clear the Queue
    """
    queue.queue.clear()
    
    return {
        "message": "queue cleared",
        "queue": queue.queue
    }

# Define background processor function
def process_and_add_to_queue(items: List[QueueItem]):
    results = []

    for item in items:
        if not item.url and not item.song_name:
            continue  # skip invalid item

        if item.song_name:
            try:
                print("Calling get_mpd_by_metadata with:", item.song_name)
                mpd_results = get_mpd_by_metadata(item.song_name)
                results.extend(mpd_results)
            except Exception as e:
                print(f"[MPD Metadata Error] {e}")
            continue

        if item.url:
            url = item.url.strip()
            result = None

            for matcher, handler in [
                (is_spotify_url, get_spotify_info),
                (is_youtube_url, get_youtube_metadata),
            ]:
                if matcher(url):
                    try:
                        print(f"running handler for url: {url}")
                        result = handler(url)
                    except Exception as e:
                        print(f"[URL Handler Error] {e}")
                    break

            if result is None:
                try:
                    result = add_raw_url(url)
                except Exception as e:
                    print(f"[Raw URL Error] {e}")

            if result:
                results.append(result)

    # Add fully processed items to queue
    if results:
        queue.add_multiple_extend(queue.queue, results)
        print(f"Added to queue in background: {results}")


class AddBeforeRequest(BaseModel):
    url: HttpUrl = Field(..., description="URL of the media to add")
    index: int = Field(..., ge=0, description="Index before which to insert the item")



@router.post("/queue/add_before")
def add_before(item: AddBeforeRequest):
    """
    Insert item before a given index in the queue.
    """
    url = item.url.strip()
    index = item.index

    if index < 0 or index > len(queue.queue):
        raise HTTPException(status_code=400, detail="Invalid index")

    result = None

    # Metadata handling
    for matcher, handler in [
        (is_spotify_url, get_spotify_info),
        (is_youtube_url, get_youtube_metadata),
    ]:
        if matcher(url):
            try:
                result = handler(url)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Handler error: {e}")
            break

    if result is None:
        try:
            result = add_raw_url(url)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Raw URL handler error: {e}")

    # Insert the result into the queue at the given index
    qlist = list(queue.queue)
    qlist.insert(index, result)
    queue.queue.clear()
    queue.queue.extend(qlist)

    return {
        "message": f"Item inserted before index {index}",
        "inserted_item": result,
        "queue_length": len(queue.queue),
    }