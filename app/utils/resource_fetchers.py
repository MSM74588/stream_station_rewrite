import yaml
import socket
import os

def load_config(config_path):
    with open(config_path, "r") as f:
        return yaml.safe_load(f)
    
def save_auth(data, auth_path):
    with open(auth_path, "w") as f:
        yaml.safe_dump(data, f)

def load_auth(auth_path):
    if not os.path.exists(auth_path):
        return None
    with open(auth_path, "r") as f:
        return yaml.safe_load(f)
    
def get_lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # Doesn't send data, just opens socket
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# def get_mpd_by_metadata(song_name: str) -> Optional[SongMetadataModel]:
#     if not song_name:
#         raise ValueError("Song Name not Provided")

#     try:
#         # Search for the song and get the first matching file path
#         search_cmd = ["mpc", "search", "title", song_name]
#         result = subprocess.run(search_cmd, capture_output=True, text=True, check=True)
#         lines = result.stdout.strip().split("\n")

#         if not lines or not lines[0]:
#             return None

#         # Use mpc with format to get metadata of the first match
#         metadata_cmd = [
#             "mpc",
#             "-f",
#             "%title%\n%artist%\n%album%\n%time%",
#             "search",
#             "title",
#             song_name
#         ]
#         metadata_result = subprocess.run(metadata_cmd, capture_output=True, text=True, check=True)
#         meta_lines = metadata_result.stdout.strip().split("\n")

#         if len(meta_lines) < 4:
#             return None  # incomplete metadata

#         title = meta_lines[0].strip()
#         artist = meta_lines[1].strip()
#         album = meta_lines[2].strip()
#         duration_str = meta_lines[3].strip()

#         # Convert duration from mm:ss to seconds
#         minutes, seconds = map(int, duration_str.split(":"))
#         duration_seconds = minutes * 60 + seconds

#         return SongMetadataModel(
#             song_name=title,
#             artist=artist,
#             album=album,
#             duration=duration_seconds
#         )

#     except subprocess.CalledProcessError as e:
#         print("Error running mpc:", e)
#         return None
#     except Exception as e:
#         print("Unexpected error:", e)
#         return None

