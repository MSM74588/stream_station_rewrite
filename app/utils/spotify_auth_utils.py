import os
from ..constants import AUTH_PATH, CONFIG_PATH, SPOTIFY_SCOPES
import yaml
import spotipy
import time
from spotipy.oauth2 import SpotifyOAuth
from .resource_fetchers import load_config, load_auth, save_auth





# def is_spotify_setup():
#     return os.path.exists(AUTH_PATH)

REQUIRED_KEYS = [
    "access_token",
    "refresh_token",
    "scope",
    "token_type"
]

def is_spotify_setup():
    if not os.path.exists(AUTH_PATH):
        return False
    
    try:
        with open(AUTH_PATH, "r") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        print(f"Failed to read auth file: {e}")
        return False

    # Check that all required keys exist and are not empty
    for key in REQUIRED_KEYS:
        if not data.get(key):
            print(f"Missing or empty Spotify auth key: {key}")
            return False
    
    return True

def load_spotify_auth():
    auth = load_auth(AUTH_PATH)
    config = load_config(CONFIG_PATH)
    
    if not config or not all(k in config for k in ("spotify_client_id", "spotify_client_secret", "spotify_redirect_uri")):
        raise ValueError("Spotify configuration is incomplete. Please check your config.yaml.")
    
    if auth and "access_token" in auth and "expires_at" in auth:
        if auth["expires_at"] > int(time.time()):
                sp = spotipy.Spotify(auth=auth["access_token"])
                return sp
                # RETURN THIS????
        else:
                sp_oauth = SpotifyOAuth(
                    client_id=config["spotify_client_id"],
                    client_secret=config["spotify_client_secret"],
                    redirect_uri=config["spotify_redirect_uri"],
                    scope=SPOTIFY_SCOPES,
                    cache_path=AUTH_PATH
                )
                token_info = sp_oauth.refresh_access_token(auth["refresh_token"])
                save_auth(token_info, AUTH_PATH)
                sp = spotipy.Spotify(auth=token_info["access_token"])
                return sp
                # RETURN THIS????
    
    else:
            sp_oauth = SpotifyOAuth(
                client_id=config["spotify_client_id"],
                client_secret=config["spotify_client_secret"],
                redirect_uri=config["spotify_redirect_uri"],
                scope=SPOTIFY_SCOPES,
                cache_path=AUTH_PATH
            )
            token_info = sp_oauth.get_access_token(as_dict=True)
            save_auth(token_info, AUTH_PATH)
            sp = spotipy.Spotify(auth=token_info["access_token"])
            return sp
            # RETURN THIS????
            
            