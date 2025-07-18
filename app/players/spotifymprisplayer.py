from ..utils.command import control_playerctl
import time
import subprocess
from .mediaplayerbase import MediaPlayerBase
from ..utils.player_utils import get_playerctl_data

class SpotifyMPRISPlayer(MediaPlayerBase):
    def __init__(self, spotify_id: str):
        self.spotify_id = spotify_id
        self.type: str = "spotify"
        self.is_paused: bool = False
        self.unloaded: bool = False  # Public as requested

        if not spotify_id:
            raise ValueError("No Spotify ID provided")

        # Open the track in Spotify
        subprocess.run(["xdg-open", f"spotify:track:{spotify_id}"], check=True)
        time.sleep(2)  # Wait for Spotify to become responsive

        # Disable repeat
        control_playerctl("--player=spotify loop None")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.unload()

    def unload(self):
        if not self.unloaded:
            self.stop()
            self.unloaded = True

    def __del__(self):
        print(f"Cleaning up SpotifyMPRISPlayer for: {self.spotify_id}")
        self.unload()

    def play(self):
        if self.is_paused:
            control_playerctl("--player=spotify play")

    def pause(self):
        self.is_paused = True
        control_playerctl("--player=spotify pause")

    def stop(self):
        control_playerctl("--player=spotify stop")

    def set_repeat(self): # type: ignore
        try:
            result = subprocess.run(
                ["playerctl", "--player=spotify", "loop"],
                capture_output=True,
                text=True
            )
            current_loop = result.stdout.strip()
            print(f"Current loop status: {current_loop}")

            if current_loop == "None":
                subprocess.run(["playerctl", "--player=spotify", "loop", "Track"])
                print("Loop mode set to 'Track'.")
                return "on"
            else:
                subprocess.run(["playerctl", "--player=spotify", "loop", "None"])
                print("Loop mode set to 'None'.")
                return "off"
        except Exception as e:
            print(f"⚠️ Failed to toggle loop mode: {e}")
            return None

    def get_state(self):
        try:
            time.sleep(2)
            return get_playerctl_data(player="spotify")
        except Exception as e:
            print(f"Error getting SpotifyMPRISPlayer state: {e}")
            return None

    def get_volume(self) -> int:
        try:
            result = subprocess.run(
                ["playerctl", "--player=spotify", "volume"],
                capture_output=True,
                text=True
            )
            output = result.stdout.strip()
            if output:
                return int(round(float(output) * 100))
        except Exception as e:
            print(f"⚠️ Failed to get Spotify volume: {e}")
        return -1

    def set_volume(self, volume: int):
        if not (0 <= volume <= 100):
            raise ValueError("Volume must be between 0 and 100.")
        scaled_vol = volume / 100
        control_playerctl(f"--player=spotify volume {scaled_vol}")

    def get_progress(self) -> int:
        try:
            result = subprocess.run(
                ["playerctl", "--player=spotify", "position"],
                capture_output=True,
                text=True
            )
            output = result.stdout.strip()
            if output:
                return int(float(output))
        except Exception as e:
            print(f"⚠️ Failed to get Spotify progress: {e}")
        return -1
