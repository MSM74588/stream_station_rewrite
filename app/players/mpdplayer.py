import asyncio
import shlex
from ..constants import MPD_PORT
from ..utils.command import control_playerctl
from ..utils.player_utils import get_playerctl_data
from .mediaplayerbase import MediaPlayerBase
from contextlib import suppress

class MPDPlayer(MediaPlayerBase):
    def __init__(self, song_name: str):
        if not song_name:
            raise ValueError("Song name must be provided for MPD playback.")

        self.song_name = song_name
        self.type = "mpd"
        self._is_paused = False
        self._unloaded = False
        print(f"MPD Player initialized with song: {self.song_name}")

    async def start(self):
        await self._load_song()

    async def _run_mpc(self, *args, check=False, capture_output=False):
        cmd = ["mpc", f"--port={MPD_PORT}", *args]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE if capture_output else None,
            stderr=asyncio.subprocess.PIPE if capture_output else None,
        )
        stdout, stderr = await process.communicate()
        return process.returncode, stdout.decode() if stdout else '', stderr.decode() if stderr else ''

    async def _load_song(self):
        await self._run_mpc("clear")
        cmd = ["mpc", f"--port={MPD_PORT}", "findadd", "title", self.song_name]
        print("🔧 Running command:", " ".join(shlex.quote(arg) for arg in cmd))

        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate()

        print("stdout:", stdout.decode().strip())
        print("stderr:", stderr.decode().strip())

        if proc.returncode != 0:
            raise ValueError(f"Song not found in MPD library: '{self.song_name}'")

    async def play(self):
        print(f"Playing song: {self.song_name}")
        if self._is_paused:
            await self._run_mpc("pause")
            self._is_paused = False
        else:
            control_playerctl("--player=mpv,spotify,mpd,firefox stop")
            await self._run_mpc("play")

    async def stop(self):
        print("Stopping MPD player.")
        await self._run_mpc("stop")

    async def pause(self):
        print("Pausing MPD player.")
        await self._run_mpc("pause")
        self._is_paused = True

    async def set_repeat(self):
        print("Toggling repeat mode.")
        _, stdout, _ = await self._run_mpc(capture_output=True)
        repeat_status = "off"

        for line in stdout.splitlines():
            if "repeat: on" in line:
                repeat_status = "on"
                break
            elif "repeat: off" in line:
                repeat_status = "off"
                break

        if repeat_status == "off":
            await self._run_mpc("repeat", "on")
            print("Repeat mode set to 'on'.")
            return "on"
        else:
            await self._run_mpc("repeat", "off")
            print("Repeat mode set to 'off'.")
            return "off"

    async def set_volume(self, volume: int):
        if not (0 <= volume <= 100):
            raise ValueError("Volume must be between 0 and 100.")
        print(f"Setting volume to {volume}.")
        await self._run_mpc("volume", str(volume))

    async def get_volume(self) -> int:
        try:
            _, stdout, _ = await self._run_mpc(capture_output=True)
            for line in stdout.splitlines():
                if "volume:" in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part.startswith("volume:"):
                            volume_str = parts[i + 1] if parts[i + 1].endswith('%') else part.split(":")[1]
                            return int(volume_str.strip('%'))
        except Exception as e:
            print(f"⚠️ Failed to get volume from MPD: {e}")
        return -1

    async def get_state(self):
        try:
            return get_playerctl_data(player="mpd")
        except Exception as e:
            print(f"⚠️ Failed to get MPD player state: {e}")
            return None

    async def get_progress(self) -> int:
        try:
            _, stdout, _ = await self._run_mpc(capture_output=True)
            for line in stdout.splitlines():
                if "/" in line and ":" in line:
                    tokens = line.strip().split()
                    for token in tokens:
                        if "/" in token and ":" in token:
                            current_time = token.split("/")[0]
                            minutes, seconds = map(int, current_time.split(":"))
                            return minutes * 60 + seconds
        except Exception as e:
            print(f"⚠️ Failed to get playback progress: {e}")
        return -1

    async def unload(self):
        if not self._unloaded:
            print(f"Unloading MPDPlayer for: {self.song_name}")
            await self.stop()
            self._unloaded = True

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.unload()
