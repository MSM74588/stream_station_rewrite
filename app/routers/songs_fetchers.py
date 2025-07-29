from fastapi import APIRouter, HTTPException, Query, Request, Body
from app.models import SpotifyLikedSongItem
from typing import List, Union, Dict
from ..utils.spotify_fetchers import fetch_liked_songs_from_spotify, get_all_liked_songs_from_db
from fastapi import Depends
from ..utils.spotify_auth_utils import is_spotify_setup

import subprocess
from pathlib import Path
from mutagen import File as MutagenFile  # type: ignore[reportPrivateImportUsage]

from ..utils.resource_fetchers import load_config
from app.constants import CONFIG_PATH

from app.constants import MUSIC_DIR
music_dir = MUSIC_DIR

router = APIRouter()

@router.get("/songs/spotify", response_model=List[SpotifyLikedSongItem], tags=["Resource Fetcher"])
def get_spotify_songs(request: Request):
    """
    Fetch liked songs from spotify, sync them to DB and the return the songs.
    if `sync` parameter is passed, then it will freshly fetch the songs from Spotify.
    else, it will return the songs from the local database.
    """
    
    if not is_spotify_setup():
        raise HTTPException(status_code=400, detail="Spotify auth is not properly set up.")
    
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
    try:
        return get_all_liked_songs_from_db()
    
    except ValueError as v:
        HTTPException(status_code=500, detail=f"Failed fetching from DB: {v}")
    
    except Exception as e:
        HTTPException(status_code=500, detail=f"Something went wrong: {e}")
        
@router.get("/songs")
def get_local_songs():
    """
    # Get All local songs via `mpc`
    """
    try:
        output = subprocess.check_output([
            "mpc", "-h", "127.0.0.1", "-p", "6601",
            "--format", "%file%|%title%|%artist%|%album%|%track%|%time%",
            "listall"
        ], text=True)
    except subprocess.CalledProcessError as e:
        return {"error": "Failed to query MPD", "details": str(e)}


    songs = []

    for line in output.strip().split("\n"):
        if not line.strip():
            continue

        parts = (line.split("|") + [""] * 6)[:6]
        file_rel, title, artist, album, track, time_str = parts
        file_path = music_dir / file_rel

        # Fallback title
        title = title or Path(file_rel).stem

        # Get file size
        try:
            size_bytes = file_path.stat().st_size
        except FileNotFoundError:
            size_bytes = None

        # Read metadata using Mutagen
        duration = None
        try:
            audio = MutagenFile(file_path, easy=True)
            
            print(f"Mutagen File: {audio}")
            
            if audio:
                metadata = audio.tags or {}

                artist = metadata.get('artist', [artist])[0] or None
                album = metadata.get('album', [album])[0] or None
                title = metadata.get('title', [title])[0] or title
                track = metadata.get('tracknumber', [track])[0] or None

                if hasattr(audio.info, 'length'):
                    duration = int(audio.info.length)
        except Exception:
            # fallback to MPD's time
            duration = int(time_str) if time_str.isdigit() else None

        songs.append({
            "file": file_rel,
            "title": title,
            "artist": artist,
            "album": album,
            "track": track,
            "duration": duration,
            "size_bytes": size_bytes,
            "size_mb": round(size_bytes / (1024 * 1024), 2) if size_bytes else None
        })

    return {"songs": songs}

config = load_config(CONFIG_PATH)

# Check if a path is allowed
def is_allowed_path(path: Path) -> bool:
    path = path.resolve()

    # Must be absolute
    if not path.is_absolute():
        return False

    # Reject symlinks (self or any parent)
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        return False

    # Must be inside allowed scopes
    if not any(scope in path.parents or scope == path for scope in ALLOWED_SCOPES):
        return False

    # Must NOT be inside forbidden scopes
    if any(path == forbidden or forbidden in path.parents for forbidden in FORBIDDEN_SCOPES):
        return False

    return True

# 🔒 Only allow access inside these secure directories
ALLOWED_SCOPES = [Path(scope).resolve() for scope in config.get("scopes", [])]
FORBIDDEN_SCOPES = [Path(fscope).resolve() for fscope in config.get("forbidden_scopes", [])]
BLOCKED_EXTENSIONS = [".env", ".db", ".sqlite", ".pem", ".key", ".crt", ".cfg", ".ini"]

@router.post("/filesystem", tags=["File System"])
def crawl_directory(dir: str = Body(..., embed=True)) -> Dict[str, List[Dict[str, Union[str, None]]]]:
    """
    Securely list files and directories inside a scoped directory,
    applying full access control, symlink & dotfile protection.
    Returns the absolute path of each item.
    """
    raw_path = Path(dir)

    if not raw_path.is_absolute():
        raise HTTPException(status_code=400, detail="Path must be absolute.")

    try:
        target_path = raw_path.resolve(strict=True)

        if not is_allowed_path(target_path):
            print(f"[ACCESS DENIED] Attempted access to: {target_path}")
            raise HTTPException(
                status_code=403,
                detail="Access denied: outside allowed scopes or in forbidden scope."
            )

        if not target_path.exists():
            raise HTTPException(status_code=404, detail="Directory does not exist.")

        if not target_path.is_dir():
            raise HTTPException(status_code=400, detail="The path is not a directory.")

        items = []
        for item in target_path.iterdir():
            try:
                resolved_item = item.resolve(strict=True)

                # Skip dotfiles
                if item.name.startswith("."):
                    continue

                # Skip if disallowed by scope rules
                if not is_allowed_path(resolved_item):
                    items.append({
                        "filename": item.name,
                        "filetype": "permission_denied",
                        "extension": None,
                        "path": str(resolved_item)
                    })
                    continue

                # Skip blocked extensions
                if item.is_file() and item.suffix.lower() in BLOCKED_EXTENSIONS:
                    continue

                is_dir = item.is_dir()
                entry = {
                    "filename": item.name,
                    "filetype": "directory" if is_dir else "file",
                    "extension": None if is_dir else item.suffix,
                    "path": str(resolved_item)
                }

                items.append(entry)

            except PermissionError:
                items.append({
                    "filename": item.name,
                    "filetype": "permission_denied",
                    "extension": None,
                    "path": str(item.absolute())
                })
            except Exception as e:
                print(f"[ERROR] While processing {item}: {e}")
                continue

        return {"items": items}

    except PermissionError:
        return {"error": "Permission denied while accessing the directory."}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Directory not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Unexpected error: {e}")
