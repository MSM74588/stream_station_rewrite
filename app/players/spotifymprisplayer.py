import asyncio
from ..utils.command import control_playerctl
from ..utils.player_utils import get_playerctl_data
from .mediaplayerbase import MediaPlayerBase


class SpotifyMPRISPlayer(MediaPlayerBase):
    def __init__(self, spotify_id: str):
        self.spotify_id = spotify_id
        self.type: str = "spotify"
        self.is_paused: bool = False
        self.unloaded: bool = False

        if not spotify_id:
            raise ValueError("No Spotify ID provided")

    async def async_init(self):
        await self._run("xdg-open", f"spotify:track:{self.spotify_id}")
        await asyncio.sleep(2)
        await self._run("playerctl", "-p", "spotify", "shuffle", "off")
        control_playerctl("--player=spotify loop None")
        return self

    async def _run(self, *args):
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        return proc.returncode, stdout.decode().strip(), stderr.decode().strip()

    async def unload(self):
        if not self.unloaded:
            await self.stop()
            self.unloaded = True

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.unload()

    def __del__(self):
        print(f"Cleaning up SpotifyMPRISPlayer for: {self.spotify_id}")

    async def play(self):
        if self.is_paused:
            control_playerctl("--player=spotify play")

    async def pause(self):
        self.is_paused = True
        control_playerctl("--player=spotify pause")

    async def stop(self):
        control_playerctl("--player=spotify stop")

    async def set_repeat(self):
        try:
            code, out, err = await self._run("playerctl", "--player=spotify", "loop")
            print(f"Current loop status: {out}")

            if out == "None":
                await self._run("playerctl", "--player=spotify", "loop", "Track")
                print("Loop mode set to 'Track'.")
                return "on"
            else:
                await self._run("playerctl", "--player=spotify", "loop", "None")
                print("Loop mode set to 'None'.")
                return "off"
        except Exception as e:
            print(f"⚠️ Failed to toggle loop mode: {e}")
            return None

    async def get_state(self):
        try:
            await asyncio.sleep(2)
            return get_playerctl_data(player="spotify")
        except Exception as e:
            print(f"Error getting SpotifyMPRISPlayer state: {e}")
            return None

    async def get_volume(self) -> int:
        try:
            code, out, err = await self._run("playerctl", "--player=spotify", "volume")
            if out:
                return int(round(float(out) * 100))
        except Exception as e:
            print(f"⚠️ Failed to get Spotify volume: {e}")
        return -1

    async def set_volume(self, volume: int):
        if not (0 <= volume <= 100):
            raise ValueError("Volume must be between 0 and 100.")
        scaled_vol = volume / 100
        control_playerctl(f"--player=spotify volume {scaled_vol}")

    async def get_progress(self) -> int:
        try:
            code, out, err = await self._run("playerctl", "--player=spotify", "position")
            if out:
                return int(float(out))
        except Exception as e:
            print(f"⚠️ Failed to get Spotify progress: {e}")
        return -1
