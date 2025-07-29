from fastapi import APIRouter, Query
import json
import subprocess
from typing import Optional, Dict, Any

router = APIRouter()


def is_youtube_url(url: str) -> Optional[str]:
    """
    Determines if a string is a YouTube video URL, playlist URL, or neither.
    You should implement robust URL parsing here.
    """
    if "youtube.com/watch?v=" in url or "youtu.be/" in url:
        return "video"
    if "youtube.com/playlist?list=" in url:
        return "playlist"
    return None 


def _get_item_type(video_data: dict) -> str:
    """
    Determines the type of item (video, live_video, etc.) based on video data.
    Implement your specific classification logic here.
    """
    if video_data.get("is_live"):
        return "live_video"
    if video_data.get("duration") is not None: # A video with a finite duration
        return "video"
    if video_data.get("entries"): # For a playlist item that might be a sub-playlist
        return "playlist"
    return "unknown" # Default for anything else, like channels in search results


def _get_thumbnail_url(video_data: dict) -> Optional[str]:
    """
    Extracts the URL of the 'best' thumbnail (highest resolution/area)
    from the 'thumbnails' list provided by yt-dlp.
    """
    thumbnails = video_data.get("thumbnails")
    
    if not thumbnails or not isinstance(thumbnails, list):
        return None

    best_thumbnail_url = None
    max_area = -1

    for thumb in thumbnails:
        url = thumb.get("url")
        # Ensure width and height are numeric and not None
        width = thumb.get("width")
        height = thumb.get("height")

        if url and isinstance(width, (int, float)) and isinstance(height, (int, float)):
            current_area = width * height
            if current_area > max_area:
                max_area = current_area
                best_thumbnail_url = url
        # Fallback if dimensions are not available but a URL exists
        elif url and best_thumbnail_url is None: # If no better thumbnail found yet
            best_thumbnail_url = url # Take the first one with a URL as a last resort

    return best_thumbnail_url


@router.get("/youtube", summary="Get YouTube video, playlist, or search results", tags=["Search"])
def yt_feed(
    search: str = Query(..., description="Search term or YouTube video/playlist URL"),
    page: int = Query(1, ge=1, description="Page number for pagination (for search only)"),
    per_page: int = Query(25, ge=1, le=50, description="Results per page (max 50)")
) -> Dict[str, Any]:
    """
    Fetches information from YouTube based on a search term or a direct URL.
    Returns detailed metadata for videos, a list of videos for playlists,
    or paginated search results.
    """
    content_type = is_youtube_url(search)
    
    try:
        if content_type == "video":
            # Get full metadata for a YouTube video
            command = ["yt-dlp", "--dump-json", search]
            output = subprocess.check_output(command, text=True, stderr=subprocess.PIPE)
            data = json.loads(output)
            
            return {
                "type": "video",
                "title": data.get("title"),
                "id": data.get("id"),
                "url": data.get("webpage_url"),
                "channel": data.get("uploader"),
                "channel_url": data.get("uploader_url"),
                "upload_date": data.get("upload_date"),
                "thumbnail": _get_thumbnail_url(data), # Use the helper function
                "duration": data.get("duration"),
                "release_timestamp": data.get("release_timestamp") or data.get("timestamp"),
                "is_live": data.get("is_live", False)
            }
        elif content_type == "playlist":
            # Get list of videos in playlist (limited metadata using --flat-playlist)
            # --flat-playlist provides less detail but is faster for large playlists
            command = ["yt-dlp", "--flat-playlist", "--dump-json", search]
            output = subprocess.check_output(command, text=True, stderr=subprocess.PIPE)
            videos = [json.loads(line) for line in output.strip().split("\n") if line.strip()]

            # Optional: Fetch full details for each video in playlist if needed
            # This would make the response much slower for large playlists
            # For this example, we stick to --flat-playlist output
            
            results = []
            for v in videos:
                # Some videos in --flat-playlist output might be placeholders or unavailable
                if v.get("_type") == "url" and v.get("id"):
                    results.append({
                        "title": v.get("title"),
                        "id": v.get("id"),
                        "url": v.get("webpage_url") or f"https://www.youtube.com/watch?v={v.get('id')}",
                        "channel": v.get("uploader"),
                        "channel_url": v.get("uploader_url"),
                        "upload_date": v.get("upload_date"),
                        "thumbnail": _get_thumbnail_url(v), # Use the helper function
                        "duration": v.get("duration"),
                        "release_timestamp": v.get("release_timestamp") or v.get("timestamp"),
                        "is_live": v.get("is_live", False)
                    })
            
            return {
                "type": "playlist",
                "total_videos": len(videos), # Total from --flat-playlist
                "results": results # Filtered/processed results
            }
        else:
            # Perform a fuzzy search
            # ytsearch<num>: means 'search and return num results'.
            # We fetch more than per_page to allow for pagination on our end.
            # Using --flat-playlist for search results for speed.
            command = [
                "yt-dlp",
                f"ytsearch{page * per_page + 10}:{search}", # Fetch a few more to be safe for pagination
                "--flat-playlist",
                "--dump-json"
            ]
            result = subprocess.check_output(command, text=True, stderr=subprocess.PIPE)
            videos = [json.loads(line) for line in result.strip().split("\n") if line.strip()]
            
            start = (page - 1) * per_page
            end = start + per_page
            paginated_videos = videos[start:end]

            processed_paginated_videos = []
            for v in paginated_videos:
                 # Filter out non-video/playlist entries if necessary, or just process them
                if v.get("_type") == "url" and v.get("id"): # Ensure it's a video/playlist item
                    processed_paginated_videos.append({
                        "title": v.get("title"),
                        "id": v.get("id"),
                        "url": v.get("webpage_url") or f"https://www.youtube.com/watch?v={v.get('id')}",
                        "channel": v.get("uploader"),
                        "channel_url": v.get("uploader_url"),
                        "upload_date": v.get("upload_date"),
                        "thumbnail": _get_thumbnail_url(v), # Use the helper function
                        "duration": v.get("duration"),
                        "release_timestamp": v.get("release_timestamp") or v.get("timestamp"),
                        "is_live": v.get("is_live", False),
                        "item_type": _get_item_type(v)
                    })

            return {
                "type": "search",
                "query": search,
                "page": page,
                "per_page": per_page,
                "results": processed_paginated_videos,
                "total_found": len(videos) # Total found by yt-dlp before pagination
            }
    except subprocess.CalledProcessError as e:
        # Capture stdout and stderr from yt-dlp for better debugging
        error_output = e.stderr if e.stderr else "No stderr output"
        return {"error": "yt-dlp failed", "detail": f"Command: {' '.join(e.cmd)}\nExit Code: {e.returncode}\nStderr: {error_output}"}
    except json.JSONDecodeError as e:
        return {"error": "Failed to parse yt-dlp output", "detail": str(e)}
    except Exception as e:
        return {"error": "Unexpected error", "detail": str(e)}




