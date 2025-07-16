from typing import Optional
import time
import subprocess
from app.models import PlayerInfo
from app.constants import MUSIC_DIR, IGNORE_PLAYERS

from pathlib import Path
import shutil

import asyncio

# PLAYERCTL DATA
def get_playerctl_data(player: Optional[str] = None) -> PlayerInfo:
    
    time.sleep(0.5) 
    # To settle the playing state, since dbus is updated asynchronously,
    # so calling it instantly after setting state will still return the previous value.
    
    def run_playerctl_command(args):
        cmd = ["playerctl", f"--ignore-player={IGNORE_PLAYERS}"]
        if player:
            cmd += ["--player", player]
        cmd += args
        try:
            return subprocess.check_output(cmd, text=True).strip()
        except subprocess.CalledProcessError:
            return None
        except FileNotFoundError:
            print("playerctl not found.")
            return None

    # Fetch data
    status = run_playerctl_command(["status"]) or "Stopped"
    title = run_playerctl_command(["metadata", "xesam:title"]) or ""
    artist = run_playerctl_command(["metadata", "xesam:artist"]) or ""
    url = run_playerctl_command(["metadata", "xesam:url"]) or ""
    volume = run_playerctl_command(["volume"]) or "0"
    duration_us = run_playerctl_command(["metadata", "mpris:length"]) or "0"
    position_us = run_playerctl_command(["position"]) or "0"

    # Convert microseconds to seconds
    def to_seconds(us):
        try:
            return int(float(us)) // 1_000_000
        except (ValueError, TypeError):
            return 0

    # Final object
    return PlayerInfo(
        status=status.lower(),
        current_media_type="audio",  # You can detect more accurately if needed
        volume=int(float(volume) * 100),  # Convert to 0–100 scale
        is_paused=(status.lower() != "playing"),
        cache_size=0,  # You can implement this if relevant
        media_name=title,
        media_uploader=artist,
        media_duration=to_seconds(duration_us),
        media_progress=to_seconds(position_us),
        media_url=url
    )
    
# INITIALISE MPD

from app.variables import mpd_proc, mpdirs2_proc
import signal
import asyncio

async def init_mpd_mpdris(mpd_port):
    global mpd_proc, mpdirs2_proc
    
    mpdris2_path = shutil.which("mpDris2")
    
    project_dir = Path(__file__).resolve().parent.parent / "mpd"

    print(f"Project directory: {project_dir}")

    state_dir = project_dir / "state"
    state_dir.mkdir(exist_ok=True)
    music_dir = MUSIC_DIR.resolve()
    music_dir.mkdir(parents=True, exist_ok=True)
    # --- Write mpd.conf dynamically ---
    mpd_config = project_dir / "mpd.conf"
    mpd_config.write_text(f"""
music_directory        "{music_dir}"
playlist_directory     "{state_dir}/playlists"
db_file                "{state_dir}/database"
log_file               "{state_dir}/mpd.log"
pid_file               "{state_dir}/mpd.pid"
state_file             "{state_dir}/state"
sticker_file           "{state_dir}/sticker.sql"
bind_to_address        "127.0.0.1"
port                   "{mpd_port}"

auto_update            "yes"
auto_update_depth      "0"

audio_output {{
    type                "alsa"
    name                "Software Volume"
    mixer_type          "software"
}}

""")
    # --- Start MPD ---
    mpd_proc = subprocess.Popen(
        ["mpd", "--no-daemon", str(mpd_config)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    # Wait for MPD socket to become available
    for _ in range(20):
        if mpd_proc.poll() is not None:
            raise RuntimeError("MPD exited early — check mpd.conf or logs")
        try:
            reader, writer = await asyncio.open_connection("127.0.0.1", 6601)
            writer.close()
            await writer.wait_closed()
            break
        except OSError:
            await asyncio.sleep(0.1)
    else:
        raise RuntimeError("MPD socket did not become available")
    
    # Clear MPD's current playlist
    subprocess.run(["mpc", f"--port={mpd_port}", "clear"])
    subprocess.run(["mpc", f"--port={mpd_port}", "stop"])
    
    print(f"✅ MPD started with music dir: {MUSIC_DIR}")
  # --- Run `mpc update` to update the DB ---
    try:
        subprocess.run(["mpc", "-h", "127.0.0.1", "-p", f"{mpd_port}", "update"], check=True)
        print("📂 MPD music database updated")
    except subprocess.CalledProcessError as e:
        print(f"⚠️ Failed to run `mpc update`: {e}")
    mpdirs2_proc = subprocess.Popen([
        # HAVE TO ADD python3 as dbus is not available inside venv interpreter.
        "/usr/bin/python3",
        mpdris2_path,
        "--port", f"{mpd_port}",
    ]) # type: ignore
    print("✅ mpdirs2 started")

async def cleanup_mpd_mpdris():
    if mpdirs2_proc and mpdirs2_proc.poll() is None:
        mpdirs2_proc.send_signal(signal.SIGTERM)
        try:
            mpdirs2_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            mpdirs2_proc.kill()
            mpdirs2_proc.wait()
        print("🛑 mpdirs2 stopped")

    # --- On Shutdown: Stop MPD ---
    if mpd_proc and mpd_proc.poll() is None:
        mpd_proc.send_signal(signal.SIGTERM)
        try:
            mpd_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            mpd_proc.kill()
            mpd_proc.wait()
        print("🛑 MPD stopped")