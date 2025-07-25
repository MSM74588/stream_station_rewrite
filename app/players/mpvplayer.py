import subprocess
import json
import os
import socket
import time
import uuid
import threading
from typing import Optional
from .mediaplayerbase import MediaPlayerBase

class MPVMediaPlayer(MediaPlayerBase):
    def __init__(self, url):
        if not url:
            raise ValueError("A valid URL must be provided to initialize MediaPlayerManager.")

        self.url = url
        self.info = {}
        self.ipc_path = f"/tmp/mpv_socket_{uuid.uuid4().hex[:8]}"  # Unique socket path
        self.process: 'Optional[subprocess.Popen]' = None
        self.type = "mpv"

        # Only fetch metadata if it's a YouTube link
        if "youtube.com" in url or "youtu.be" in url:
            print(f"🌍 URL: {url}")
            try:
                result = subprocess.run(
                    ['yt-dlp', '--dump-json', url],
                    capture_output=True,
                    text=True,
                    check=True
                )
                self.info = json.loads(result.stdout)
                print("Metadata loaded successfully.")
            except Exception as e:
                print("Failed to fetch metadata:", e)
        

        # Start mpv with IPC enabled
        try:
            self.process = subprocess.Popen([
                'mpv',
                url,
                '--no-terminal',
                '--no-video',
                '--force-window=no',
                '--player-operation-mode=pseudo-gui',
                f'--input-ipc-server={self.ipc_path}'
            ])
            print(f"Started mpv with IPC at {self.ipc_path}")

            # Wait for the socket to appear
            for _ in range(20):
                if os.path.exists(self.ipc_path):
                    break
                time.sleep(0.1)
            else:
                raise RuntimeError("IPC socket not created in time.")

        except Exception as e:
            print("❌ Failed to start mpv:", e)

        self._monitor_thread = threading.Thread(target=self._monitor_cache, daemon=True)
        self._stop_monitor = threading.Event()
        self._monitor_thread.start()

    def _send_ipc_command(self, command: dict):
        """Send a command to the mpv IPC socket."""
        try:
            with socket.socket(socket.AF_UNIX) as client:
                client.connect(self.ipc_path)
                client.sendall((json.dumps(command) + '\n').encode('utf-8'))
        except Exception as e:
            print(f"⚠️ IPC command failed: {e}")

    def play(self):
        self._send_ipc_command({"command": ["set_property", "pause", False]})
        print("▶️ Resumed playback.")

    def pause(self):
        self._send_ipc_command({"command": ["set_property", "pause", True]})
        print("⏸️ Paused playback.")

    def stop(self):
        self._stop_monitor.set()
        self._send_ipc_command({"command": ["quit"]})
        print("⏹️ Stopped playback.")
        
    def set_repeat(self):
        """
        Toggle repeat mode for mpv.
        If loop-file is 'no', set it to 'inf'. Otherwise, set it to 'no'.
        Return the new repeat status.
        """
        try:
            # Get current loop status
            with socket.socket(socket.AF_UNIX) as client:
                client.connect(self.ipc_path)
                get_command = {"command": ["get_property", "loop-file"]}
                client.sendall((json.dumps(get_command) + '\n').encode('utf-8'))
                response = client.makefile().readline()
                result = json.loads(response)
                current = result.get("data", "no")

            # Determine next state
            new_state = "yes" if current in ["no", None, False] else "no"

            # Set new loop state
            with socket.socket(socket.AF_UNIX) as client:
                client.connect(self.ipc_path)
                set_command = {"command": ["set_property", "loop-file", new_state]}
                client.sendall((json.dumps(set_command) + '\n').encode('utf-8'))

            print(f"🔁 Loop mode set to '{new_state}'.")
            return new_state

        except Exception as e:
            print(f"⚠️ Failed to toggle repeat: {e}")
            return None


    def _monitor_cache(self):
        """Monitor mpv's cache size and stop if it exceeds 1GB."""
        MAX_CACHE = 1073741824  # 1GB in bytes
        while not self._stop_monitor.is_set():
            try:
                cache_size = self._get_cache_size()
                paused = self._get_paused()
                if cache_size is not None and cache_size > MAX_CACHE:
                    print(f"⚠️ Cache size exceeded 1GB: {cache_size} bytes. Stopping player.")
                    self.stop()
                    break
                if paused and cache_size is not None and cache_size > MAX_CACHE:
                    print(f"⚠️ Cache size exceeded 1GB while paused: {cache_size} bytes. Stopping player.")
                    self.stop()
                    break
            except Exception as e:
                print(f"⚠️ Cache monitor error: {e}")
            self._stop_monitor.wait(2)  # Check every 2 seconds

    def _get_cache_size(self):
        """Get the current cache size from mpv via IPC."""
        try:
            with socket.socket(socket.AF_UNIX) as client:
                client.connect(self.ipc_path)
                command = {"command": ["get_property", "demuxer-cache-state"]}
                client.sendall((json.dumps(command) + '\n').encode('utf-8'))
                response = client.recv(4096)
                result = json.loads(response.decode('utf-8'))
                cache_state = result.get("data", {})
                return cache_state.get("cache-size", 0)
        except Exception as e:
            print(f"⚠️ Failed to get cache size: {e}")
            return None

    def _get_paused(self):
        """Check if mpv is paused via IPC."""
        try:
            with socket.socket(socket.AF_UNIX) as client:
                client.connect(self.ipc_path)
                command = {"command": ["get_property", "pause"]}
                client.sendall((json.dumps(command) + '\n').encode('utf-8'))
                response = client.recv(1024)
                result = json.loads(response.decode('utf-8'))
                return result.get("data", False)
        except Exception as e:
            print(f"⚠️ Failed to get paused state: {e}")
            return False

    # def get_state(self):
    #     return {
    #         'title': self.info.get('title'),
    #         'uploader': self.info.get('uploader'),
    #         'duration': self.info.get('duration')
    #     }
    def get_state(self):
        """
        Return a unified state dictionary for the MPV player.
        Format:
        {
            "status": "playing" | "paused" | "stopped",
            "current_media_type": "audio" | "video",
            "volume": 100,
            "is_paused": false,
            "cache_size": 0,
            "media_name": "it boy",
            "media_uploader": "bbno$",
            "media_duration": 146,
            "media_progress": 18,
            "is_live": false,
            "media_url": "https://..."
        }
        """
        try:
            # Get volume
            volume = self.get_volume()
            if volume is not None:
                volume = int(round(volume))
            else:
                volume = -1

            # Get progress
            progress = self.get_progress()
            progress = int(progress) if progress is not None else 0

            # Get paused state
            paused = self._get_paused()

            # Get cache
            cache = self._get_cache_size()
            cache = cache if cache is not None else 0

            return {
                "status": "paused" if paused else "playing" if self.is_running() else "stopped",
                "current_media_type": "audio" if "--no-video" in self.process.args else "video",
                "volume": volume,
                "is_paused": paused,
                "cache_size": cache,
                "media_name": self.info.get("title") or "Unknown",
                "media_uploader": self.info.get("uploader") or self.info.get("channel") or "Unknown",
                "media_duration": self.info.get("duration") or 0,
                "media_progress": progress,
                "is_live": self.info.get("is_live") or False,
                "media_url": self.info.get("webpage_url") or self.url,
            }
        except Exception as e:
            print(f"⚠️ Failed to get MPV state: {e}")
            return {}


    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def get_volume(self) -> Optional[float]:
        """Get the current volume level of mpv."""
        try:
            with socket.socket(socket.AF_UNIX) as client:
                client.connect(self.ipc_path)
                command = {"command": ["get_property", "volume"]}
                client.sendall((json.dumps(command) + '\n').encode('utf-8'))
                response = client.makefile().readline()
                result = json.loads(response)
                return result.get("data")
        except Exception as e:
            print(f"⚠️ Failed to get volume: {e}")
            return None
        
    def set_volume(self, volume: int):
        """
        Set the volume of the MPV player.
        Accepts values from 0 to 150.
        """
        if not (0 <= volume <= 150):
            raise ValueError("Volume must be between 0 and 150.")

        try:
            with socket.socket(socket.AF_UNIX) as client:
                client.connect(self.ipc_path)
                command = {"command": ["set_property", "volume", volume]}
                client.sendall((json.dumps(command) + '\n').encode('utf-8'))
                print(f"🔊 Volume set to {volume}")
        except Exception as e:
            print(f"⚠️ Failed to set volume: {e}")

        
    

    def get_progress(self) -> Optional[float]: # type: ignore
        """Get the current playback position (in seconds) from mpv."""
        try:
            with socket.socket(socket.AF_UNIX) as client:
                client.connect(self.ipc_path)
                command = {"command": ["get_property", "time-pos"]}
                client.sendall((json.dumps(command) + '\n').encode('utf-8'))
                response = client.makefile().readline()
                result = json.loads(response)
                return result.get("data")
        except Exception as e:
            print(f"⚠️ Failed to get playback progress: {e}")
            return None
        
    def __del__(self):
        print(f"Cleaning up MPVMediaPlayer for: {self.url}")
        if self.process:
            self.stop()
        if os.path.exists(self.ipc_path):
            os.remove(self.ipc_path)
            print(f"Removed IPC socket at {self.ipc_path}")
        else:
            print(f"IPC socket {self.ipc_path} does not exist.")



# Test runner
if __name__ == "__main__":
    # test_url = 'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
    test_url = 'https://www.youtube.com/watch?v=jfKfPfyJRdk'
    player = MPVMediaPlayer(test_url)

    print("\n=== get_state() ===")
    state = player.get_state()
    for key, value in state.items():
        print(f"{key.capitalize()}: {value if value is not None else 'N/A'}")

    # Optional controls for testing
    print(player.get_state().get('media_type'))
    time.sleep(120)
    player.pause()
    time.sleep(10)
    player.play()
    print(player.get_state().get('progress_seconds', 'N/A'))
    time.sleep(10)
    player.stop()
