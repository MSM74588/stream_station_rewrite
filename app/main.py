from fastapi import FastAPI, Depends
from sqlmodel import Session
from contextlib import asynccontextmanager


import time

import asyncio

from fastapi.middleware.cors import CORSMiddleware


from fastapi import WebSocket, WebSocketDisconnect
import json

from app.models import Item
from app.crud import get_items, create_item

from app.routers import player  # Import your router
from app.routers import spotify_tasks
from app.routers import songs_fetchers

from app.constants import VERSION, COVER_ART_PATH, MUSIC_DIR, MPD_PORT, DATABASE_URL

from app.utils.check_utils import check_dependencies

from fastapi.staticfiles import StaticFiles

from app.utils.player_utils import *

from app.variables import mpd_proc, mpdirs2_proc, player_instance

from app.database import create_db_and_tables, create_engine, get_session

from .utils.command import control_playerctl

tags_metadata = [
    {
        "name": "Server Status",
        "description": "Get the status of the server.",
    },
    {
        "name": "Player",
        "description": "Manage the Player. Play Media. Control: Play, Pause, Stop",
        "externalDocs": {
            "description": "Items external docs",
            "url": "https://fastapi.tiangolo.com/",
        },
    },
]



# --- Setup database ---


# --- Lifespan ---


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run this on startup
    check_dependencies()
    
    # MAKE FOLDER STRUCTURE
    COVER_ART_PATH.mkdir(parents=True, exist_ok=True)
    
    await init_mpd_mpdris(MPD_PORT) 
    
    global player_instance
    if player_instance is not None:
        player_instance.stop()
        del player_instance
        player_instance = None
    
    # STOP ANY EXISTING PLAYERS VIA MPRIS
    control_playerctl("--player=mpv,spotify,mpd,firefox stop")
    

    create_db_and_tables()
    print("✅ SQLite DB and tables ready")
    yield
    # (Optional) Clean-up logic here
    
    await cleanup_mpd_mpdris()
        
    if player_instance is not None:
        player_instance.stop()
        del player_instance
        player_instance = None

# --- FastAPI App ---
app = FastAPI(
    title="Stream Station Renaissance",
    description="System to stream media from YouTube and Spotify to local speakers or Chromecast devices.",
    version=VERSION,
    openapi_tags=tags_metadata,
    lifespan=lifespan
)

app.include_router(player.router, prefix="/player")
app.include_router(spotify_tasks.router)
app.include_router(songs_fetchers.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or ["http://localhost:3000"] if you want to restrict
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

start_time = time.monotonic()

# SERVE COVER ART STATIC FILES
app.mount("/assets/coverarts", StaticFiles(directory=str(COVER_ART_PATH)), name="liked_songs_cover_art")



# ROUTES ------------------------------------------------------- #
@app.get("/", tags=["Server Status"], summary="Get server status")
def server_status():
    """
    # Get Server Status
    """
    uptime_seconds = time.monotonic() - start_time
    return {
        "uptime_seconds": round(uptime_seconds, 2),
        "version": VERSION,
        "status": "running",
        "player_status": "stopped"
        }


@app.post("/items/", response_model=Item)
def create_new_item(item: Item, session: Session = Depends(get_session)):
    return create_item(session, item)

@app.get("/items/", response_model=list[Item])
def read_items(session: Session = Depends(get_session)):
    return get_items(session)

@app.websocket("/ws/items")
async def websocket_items(websocket: WebSocket):
    await websocket.accept()
    print("🔌 WebSocket client connected")

    async def ping_loop():
        while True:
            try:
                await asyncio.sleep(10)
                await websocket.send_text(json.dumps({"type": "ping", "message": "pong"}))
                print("🔁 Sent ping to client")
            except Exception as e:
                print("⚠️ Ping failed:", e)
                break

    # Start ping task
    ping_task = asyncio.create_task(ping_loop())

    try:
        while True:
            message = await websocket.receive_text()
            print("📨 Received:", message)

            try:
                data = json.loads(message)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"error": "Invalid JSON"}))
                continue

            command = data.get("action")

            if command == "get_items":
                with Session(engine) as session:
                    items = get_items(session)
                    await websocket.send_text(json.dumps({
                        "action": "items",
                        "data": [item.model_dump() for item in items]
                    }))

            elif command == "add_item":
                item_data = data.get("data")
                if not item_data:
                    await websocket.send_text(json.dumps({"error": "Missing item data"}))
                    continue
                try:
                    new_item = Item(**item_data)
                    with Session(engine) as session:
                        created = create_item(session, new_item)
                    await websocket.send_text(json.dumps({
                        "action": "item_added",
                        "data": created.model_dump()
                    }))
                except Exception as e:
                    await websocket.send_text(json.dumps({"error": str(e)}))
            else:
                await websocket.send_text(json.dumps({"error": "Unknown action"}))

    except WebSocketDisconnect:
        print("❌ WebSocket client disconnected")

    finally:
        ping_task.cancel()
        try:
            await ping_task
        except asyncio.CancelledError:
            pass