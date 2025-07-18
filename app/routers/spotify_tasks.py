from fastapi import APIRouter, Request
from ..utils.spotify_auth_utils import load_config
from ..constants import AUTH_PATH, SPOTIFY_SCOPES, CONFIG_PATH
from fastapi.responses import HTMLResponse, RedirectResponse
from ..utils.resource_fetchers import get_lan_ip, load_config, save_auth
from spotipy.oauth2 import SpotifyOAuth
from ..utils.templates import render_spotify_setup_page
import requests

router = APIRouter()


@router.post("/setup", tags=["Spotify Login and Auth"])
@router.get("/setup", tags=["Spotify Login and Auth"])
def setup():
    """
    Visual Login Page to start the OAuth Workflow and get the credentials and tokens, GUI
    """
    config = load_config(CONFIG_PATH)
    client_id = config.get('spotify_client_id', 'NOT SET') if config else 'NOT SET'
    client_secret_status = 'SET' if config and config.get('spotify_client_secret') else 'NOT SET'
    lan_ip = get_lan_ip()
    html = render_spotify_setup_page(client_id, client_secret_status, lan_ip)
    return HTMLResponse(content=html)

@router.get("/auth/spotify", tags=["Spotify Login and Auth"])
def auth_spotify():
    """
    Starts Authentication workflow. Redirects to Spotify OAuth Page.
    """
    config = load_config(CONFIG_PATH)
    print(f"CONFIG: {config}")
    if not config or not all(k in config for k in ("spotify_client_id", "spotify_client_secret", "spotify_redirect_uri")):
        return HTMLResponse("<h3>Spotify configuration is missing or incomplete in config.yaml.</h3>", status_code=500)
    sp_oauth = SpotifyOAuth(
        client_id=config["spotify_client_id"],
        client_secret=config["spotify_client_secret"],
        redirect_uri=config["spotify_redirect_uri"],
        scope=SPOTIFY_SCOPES,  # <-- use the correct scopes here
        cache_path=AUTH_PATH
    )
    auth_url = sp_oauth.get_authorize_url()
    print(f"AUTH URL: {auth_url}")
    return RedirectResponse(auth_url)

@router.get("/auth/spotify/callback", tags=["Spotify Login and Auth"])
def spotify_callback(request: Request):
    """
    Processes the Token returned by Spotify Login OAuth API, And also shows it into a Visual form.
    """
    code = request.query_params.get("code")
    if not code:
        return HTMLResponse("<h3>No authorization code received.</h3>", status_code=400)

    config = load_config(CONFIG_PATH)
    if not config or not all(k in config for k in ("spotify_client_id", "spotify_client_secret", "spotify_redirect_uri")):
        return HTMLResponse("<h3>Spotify configuration is missing or incomplete in config.yaml.</h3>", status_code=500)

    sp_oauth = SpotifyOAuth(
        client_id=config["spotify_client_id"],
        client_secret=config["spotify_client_secret"],
        redirect_uri=config["spotify_redirect_uri"],
        scope=SPOTIFY_SCOPES,
        cache_path=AUTH_PATH
    )

    try:
        token_info = sp_oauth.get_access_token(code, as_dict=True)
        if not token_info:
            return HTMLResponse("<h3>Failed to get access token from Spotify.</h3>", status_code=400)

        save_auth(token_info,AUTH_PATH)

        access_token = token_info.get("access_token")
        refresh_token = token_info.get("refresh_token")
        expires_in = token_info.get("expires_in")

        return HTMLResponse(f"""
            <html>
            <head>
                <title>Spotify Auth Success</title>
                <style>
                    body {{ font-family: sans-serif; background-color: #f9f9f9; padding: 2em; }}
                    textarea {{ width: 100%; height: 100px; padding: 0.5em; font-family: monospace; }}
                    .info {{ margin-top: 1em; background: #fff; padding: 1em; border: 1px solid #ccc; }}
                </style>
            </head>
            <body>
                <h2>Spotify Authentication Successful</h2>
                <p>Copy your access token below:</p>
                <textarea readonly>{access_token}</textarea>
                <div class="info">
                    <p><strong>Refresh Token:</strong> {refresh_token}</p>
                    <p><strong>Expires In:</strong> {expires_in} seconds</p>
                </div>
                <p>You may now close this page.</p>
            </body>
            </html>
        """)
    except Exception as e:
        return HTMLResponse(f"<h3>Error exchanging code for token: {e}</h3>", status_code=500)
    







# @app.get("/tasks/fetch_spotify_songs")
# def get_spotify_songs():
#     init_spotify_db()
#     # If DB is empty, fetch from Spotify and save
#     songs = get_songs_from_db()
#     if not songs:
#         try:
#             songs = fetch_liked_songs_from_spotify()
#             save_songs_to_db(songs)
#         except Exception as e:
#             raise HTTPException(status_code=500, detail=f"Failed to fetch from Spotify: {e}")
#     return songs
    # Modify this to accept a parameter to manually sync when needed

# @app.post("/sync/spotify")
# def sync_spotify_songs():
#     """
#     Manually fetch liked songs from Spotify and update the local database.
#     """
#     try:
#         songs = fetch_liked_songs_from_spotify()
#         save_songs_to_db(songs)
#         return {"status": "success", "synced_count": len(songs)}
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Failed to sync from Spotify: {e}")