import subprocess
from ..constants import MPD_PORT
import shlex
from ..utils.command import control_playerctl
from ..utils.player_utils import get_playerctl_data

class MPDPlayer:
    def __init__(self, song_name: str):
        self.song_name = song_name
        self.info = None
        
        self.type: str = "mpd"
        
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
        Set repeat mode for the MPD player.
        """
        print("Setting repeat mode for MPD player.")
        subprocess.run(["mpc", f"--port={MPD_PORT}", "repeat", "on"], check=False)
        
    def set_volume(self, volume: int):
        """
        Set the volume for the MPD player.
        """
        if not (0 <= volume <= 100):
            raise ValueError("Volume must be between 0 and 100.")
        
        print(f"Setting MPD player volume to {volume}.")
        subprocess.run(["mpc", f"--port={MPD_PORT}", "volume", str(volume)], check=False)
        
    def get_state(self):
        """
        Get the current state of the MPD player.
        """
        try:
            return get_playerctl_data(player="mpd")
        except Exception as e:
            print(f"Error getting MPD player state: {e}")
            return None
        
    def __del__(self):
        print(f"Cleaning up MPDPlayer for: {self.song_name}")
        # Run your cleanup command here
        self.stop()  # For example, stop playback