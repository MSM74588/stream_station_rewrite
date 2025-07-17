from datetime import datetime, timezone
from sqlmodel import Session
from app.database import engine
from app.models import History
import subprocess
import asyncio

async def log_history(player_type: str, song_name: str):
    """
    Log a song into the history database using the provided song_name and data extracted from playerctl.
    """
    try:
        await asyncio.sleep(3)  # wait for player to initialize (if needed)

        def run(cmd):
            try:
                return subprocess.check_output(cmd, text=True).strip()
            except subprocess.CalledProcessError:
                return ""
            except FileNotFoundError:
                print("playerctl not found.")
                return ""

        base_cmd = ["playerctl", "--player", player_type]

        artist = run(base_cmd + ["metadata", "xesam:artist"])
        url = run(base_cmd + ["metadata", "xesam:url"])
        duration_us = run(base_cmd + ["metadata", "mpris:length"])

        # Convert microseconds to seconds
        try:
            duration_sec = int(float(duration_us)) // 1_000_000
        except (ValueError, TypeError):
            duration_sec = 0

        utc_now_str = datetime.now(timezone.utc).isoformat()

        history_entry = History(
            song_name=song_name,
            time=utc_now_str,
            duration=duration_sec,
            url=url or "",
            player_type=player_type
        )

        with Session(engine) as session:
            session.add(history_entry)
            session.commit()

        print(f"✅ History logged for {song_name} [{player_type}]")
        return True

    except Exception as e:
        print(f"❌ Failed to log history: {e}")
        return False
