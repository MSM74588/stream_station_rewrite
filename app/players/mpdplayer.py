import subprocess
from ..constants import MPD_PORT
import shlex
from ..utils.command import control_playerctl
from ..utils.player_utils import get_playerctl_data
from .mediaplayerbase import MediaPlayerBase


class MPDPlayer(MediaPlayerBase):
    def __init__(self, song_name: str):
        self.song_name = song_name
        self.info = None
        
        self.type: str = "mpd"
        self.is_puased: bool = False
        
        if not song_name:
            raise ValueError("Song name must be provided for MPD playback.")
        # Initialize MPD connection and other necessary attributes here
        print(f"MPD Player initialized with song: {self.song_name}")
        
        # Clear MPD playlist (optional)
        subprocess.run(["mpc", f"--port={MPD_PORT}", "clear"], check=False)
        
        # Try to find and add song by title
        cmd = ["mpc", f"--port={MPD_PORT}", "findadd", "title", song_name]
        print("🔧 Running command:", " ".join(shlex.quote(arg) for arg in cmd))
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        print("stdout:", result.stdout.strip())
        print("stderr:", result.stderr.strip())

        if result.returncode != 0:
            raise ValueError(f"Song not found in MPD library: '{song_name}'")

    def play(self):
        """
        Play the song in MPD.
        """
        print(f"Playing song: {self.song_name}")
        
        if self.is_puased:
            subprocess.run(["mpc", f"--port={MPD_PORT}", "pause"], check=False)
        else:
            control_playerctl("--player=mpv,spotify,mpd,firefox stop")
            subprocess.run(["mpc", f"--port={MPD_PORT}", "play"], check=False)
        
    def stop(self):
        """
        Stop the MPD player.
        """
        print("Stopping MPD player.")
        subprocess.run(["mpc", f"--port={MPD_PORT}", "stop"], check=False)
        
    def pause(self):
        """
        Pause the MPD player.
        """
        print("Pausing MPD player.")
        subprocess.run(["mpc", f"--port={MPD_PORT}", "pause"], check=False)
        
    def set_repeat(self):
        """
        Toggle repeat mode for the MPD player using mpc.
        If repeat is off, turn it on. If it's on, turn it off.
        Return the new repeat status: 'on' or 'off'.
        """
        print("Setting repeat mode for MPD player.")

        # Get current status
        result = subprocess.run(
            ["mpc", f"--port={MPD_PORT}"],
            capture_output=True,
            text=True
        )
        
        output = result.stdout
        repeat_status = "off"
        
        # Look for "[repeat: on]" or "[repeat: off]"
        for line in output.splitlines():
            if "repeat: on" in line:
                repeat_status = "on"
                break
            elif "repeat: off" in line:
                repeat_status = "off"
                break

        # Toggle repeat mode
        if repeat_status == "off":
            subprocess.run(["mpc", f"--port={MPD_PORT}", "repeat", "on"])
            print("Repeat mode set to 'on'.")
            return "on"
        else:
            subprocess.run(["mpc", f"--port={MPD_PORT}", "repeat", "off"])
            print("Repeat mode set to 'off'.")
            return "off"

        
    def set_volume(self, volume: int):
        """
        Set the volume for the MPD player.
        """
        if not (0 <= volume <= 100):
            raise ValueError("Volume must be between 0 and 100.")
        
        print(f"Setting MPD player volume to {volume}.")
        subprocess.run(["mpc", f"--port={MPD_PORT}", "volume", str(volume)], check=False)
        
    def get_volume(self) -> int:
        """
        Get the current volume level of the MPD player.
        Returns the volume as an integer between 0 and 100.
        """
        try:
            result = subprocess.run(
                ["mpc", f"--port={MPD_PORT}"],
                capture_output=True,
                text=True
            )
            for line in result.stdout.splitlines():
                if "volume:" in line:
                    # Example line: "volume: 85%   repeat: off   random: off"
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part.startswith("volume:"):
                            volume_str = parts[i + 1] if parts[i + 1].endswith('%') else part.split(":")[1]
                            return int(volume_str.strip('%'))
        except Exception as e:
            print(f"⚠️ Failed to get volume from MPD: {e}")
        return -1  # -1 indicates error
        
        
    def get_state(self):
        """
        Get the current state of the MPD player.
        """
        try:
            return get_playerctl_data(player="mpd")
        except Exception as e:
            print(f"Error getting MPD player state: {e}")
            return None
        
    def get_progress(self) -> int:
        """
        Get the current playback progress of the MPD player in seconds.
        """
        try:
            result = subprocess.run(
                ["mpc", f"--port={MPD_PORT}"],
                capture_output=True,
                text=True
            )
            for line in result.stdout.splitlines():
                if "/" in line and ":" in line:
                    # Look for a token like 0:35/3:45
                    tokens = line.strip().split()
                    for token in tokens:
                        if "/" in token and ":" in token:
                            current_time = token.split("/")[0]  # e.g., "0:35"
                            minutes, seconds = map(int, current_time.split(":"))
                            return minutes * 60 + seconds
        except Exception as e:
            print(f"⚠️ Failed to get MPD playback progress: {e}")
        return -1  # -1 indicates error


        
    def __del__(self):
        print(f"Cleaning up MPDPlayer for: {self.song_name}")
        # Run your cleanup command here
        self.stop()  # For example, stop playback