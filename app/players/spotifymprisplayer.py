from ..utils.command import control_playerctl
import time
from ..utils.player_utils import get_playerctl_data

import subprocess

class SpotifyMPRISPlayer:
    def __init__(self, spotify_id):
        self.spotify_id = spotify_id
        
        self.type: str = "spotify"
        self.is_paused: bool = False
        
        if spotify_id:
            subprocess.run(["xdg-open", f"spotify:track:{spotify_id}"], check=True)
            # Disable repeat using playerctl
            time.sleep(2)  # Wait for Spotify to initialize
            subprocess.run(["playerctl", "--player=spotify", "loop", "None"])
            # control_playerctl("loop None")
        else:
            raise ValueError("No Spotify ID provided")

    def play(self):
        # Play / pause
        # Since Spotify start play on opening just apply pause logic
        if self.is_paused:
            control_playerctl("--player=spotify play")
            
        pass
    
    def pause(self):
        """
        Pause the SpotifyMPRISPlayer.
        """
        self.is_paused = True
        control_playerctl("--player=spotify pause")
        
    def set_repeat(self):
        """
        Set repeat mode for the Spotify player.
        """
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
        # print(f"Loop mode remains '{current_loop}'.")
        # return current_loop
        
    
    def stop(self):
        control_playerctl("--player=spotify stop")
        
    def get_state(self):
        """
        Get the current state of the SpotifyMPRISPlayer.
        """
        try:
            time.sleep(2)  # Wait for Spotify to initialize
            return get_playerctl_data(player="spotify")
        except Exception as e:
            print(f"Error getting SpotifyMPRISPlayer state: {e}")
            return None
        
    def set_volume(self, volume: int):
        """
        Set the volume for the MPD player.
        """
        if not (0 <= volume <= 100):
            raise ValueError("Volume must be between 0 and 100.")
        scaled_vol = volume / 100

        control_playerctl(f"--player=spotify volume {scaled_vol}")

    def __del__(self):
        print(f"Cleaning up SpotifyMPRISPlayer for: {self.spotify_id}")
        # Run your cleanup command here
        self.stop()  # For example, stop playback