import subprocess
import shlex
import os
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
        self._load_song()

    def _run_mpc(self, *args, check=False, capture_output=False):
        cmd = ["mpc", f"--port={MPD_PORT}", *args]
        return subprocess.run(cmd, check=check, capture_output=capture_output, text=True)

    def _load_song(self):
        self._run_mpc("clear")
        cmd = ["mpc", f"--port={MPD_PORT}", "findadd", "title", self.song_name]
        print("🔧 Running command:", " ".join(shlex.quote(arg) for arg in cmd))

        result = subprocess.run(cmd, capture_output=True, text=True)
        print("stdout:", result.stdout.strip())
        print("stderr:", result.stderr.strip())

        if result.returncode != 0:
            raise ValueError(f"Song not found in MPD library: '{self.song_name}'")

    def play(self):
        print(f"Playing song: {self.song_name}")
        if self._is_paused:
            self._run_mpc("pause")
            self._is_paused = False
        else:
            control_playerctl("--player=mpv,spotify,mpd,firefox stop")
            self._run_mpc("play")

    def stop(self):
        print("Stopping MPD player.")
        self._run_mpc("stop")

    def pause(self):
        print("Pausing MPD player.")
        self._run_mpc("pause")
        self._is_paused = True

    def set_repeat(self):
        print("Toggling repeat mode.")
        result = self._run_mpc(capture_output=True)
        repeat_status = "off"

        for line in result.stdout.splitlines():
            if "repeat: on" in line:
                repeat_status = "on"
                break
            elif "repeat: off" in line:
                repeat_status = "off"
                break

        if repeat_status == "off":
            self._run_mpc("repeat", "on")
            print("Repeat mode set to 'on'.")
            return "on"
        else:
            self._run_mpc("repeat", "off")
            print("Repeat mode set to 'off'.")
            return "off"

    def set_volume(self, volume: int):
        if not (0 <= volume <= 100):
            raise ValueError("Volume must be between 0 and 100.")
        print(f"Setting volume to {volume}.")
        self._run_mpc("volume", str(volume))

    def get_volume(self) -> int:
        try:
            result = self._run_mpc(capture_output=True)
            for line in result.stdout.splitlines():
                if "volume:" in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part.startswith("volume:"):
                            volume_str = parts[i + 1] if parts[i + 1].endswith('%') else part.split(":")[1]
                            return int(volume_str.strip('%'))
        except Exception as e:
            print(f"⚠️ Failed to get volume from MPD: {e}")
        return -1

    def get_state(self):
        try:
            return get_playerctl_data(player="mpd")
        except Exception as e:
            print(f"⚠️ Failed to get MPD player state: {e}")
            return None

    def get_progress(self) -> int:
        try:
            result = self._run_mpc(capture_output=True)
            for line in result.stdout.splitlines():
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

    def unload(self):
        if not self._unloaded:
            print(f"Unloading MPDPlayer for: {self.song_name}")
            self.stop()
            self._unloaded = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unload()

    def __del__(self):
        self.unload()
