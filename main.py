import os
import json
import pandas as pd
import tidalapi

TOKEN_FILE = "tidal_token.json"
NOT_FOUND_FILE = "not_found_tracks.csv"

def save_token(session):
    """Save TIDAL OAuth token to a file."""
    token_data = {
        "token_type": session.token_type,
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "expiry_time": int(session.expiry_time.timestamp())
    }
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f)
    print("✅ Token saved successfully.")

def load_token():
    """Load TIDAL OAuth token from a file."""
    if os.path.exists(TOKEN_FILE) and os.path.getsize(TOKEN_FILE) > 0:
        with open(TOKEN_FILE, "r") as f:
            try:
                token_data = json.load(f)
                if "access_token" in token_data and "expiry_time" in token_data:
                    return token_data
            except json.JSONDecodeError:
                print("⚠️ Token file is corrupted. Re-authenticating...")
    return None

def authenticate():
    """Authenticate with TIDAL using stored tokens or OAuth login."""
    session = tidalapi.Session()
    token_data = load_token()

    if token_data:
        try:
            session.load_oauth_session(
                token_data["token_type"],
                token_data["access_token"],
                token_data["refresh_token"],
                int(token_data["expiry_time"])
            )
            if session.check_login():
                print("✅ Logged in with saved token.")
                return session
        except Exception as e:
            print(f"⚠️ Token error: {e}. Re-authenticating...")

    # Re-authenticate if token is invalid
    if os.path.exists(TOKEN_FILE):
        os.remove(TOKEN_FILE)

    session.login_oauth_simple()
    save_token(session)
    return session

def load_library():
    """Load playlist data from CSV files and merge them."""
    tidal_df = pd.read_csv("My TIDAL Library.csv")
    spotify_df = pd.read_csv("My Spotify Library.csv")
    combined_df = pd.concat([tidal_df, spotify_df]).drop_duplicates(subset="Track name", keep="first")
    return combined_df

def get_or_create_playlists(user, playlist_names):
    """Retrieve or create playlists in TIDAL."""
    existing_playlists = {p.name.lower(): p for p in user.playlists()}
    playlists = {}

    for name in playlist_names:
        name_lower = name.lower()
        if name_lower in existing_playlists:
            print(f"🎵 Playlist '{name}' already exists.")
            playlists[name_lower] = existing_playlists[name_lower]
        else:
            new_playlist = user.create_playlist(name, "Playlist created from CSV file")
            playlists[name_lower] = new_playlist
            print(f"✅ Created playlist: {name}")

    return playlists

def add_songs_to_playlists(session, user, song_data):
    """Add songs to their respective playlists, avoiding duplicates."""
    playlists = get_or_create_playlists(user, song_data["Playlist name"].unique())
    not_found_tracks = []

    for _, row in song_data.iterrows():
        playlist_name = row["Playlist name"].strip()
        track_name = row["Track name"].strip()
        artist_name = row.get("Artist name", "").strip()

        playlist = playlists.get(playlist_name.lower())
        if not playlist:
            print(f"⚠️ Playlist '{playlist_name}' not found.")
            not_found_tracks.append({"Playlist Name": playlist_name, "Track Name": track_name, "Artist Name": artist_name})
            continue

        print(f"✅ Processing playlist: {playlist.name}")

        # Check existing tracks in the playlist
        existing_tracks = {track.name.lower(): track.id for track in playlist.tracks()}

        # Search for track
        search_query = f"{track_name} {artist_name}" if artist_name else track_name
        search_result = session.search(search_query)

        if search_result and "tracks" in search_result and search_result["tracks"]:
            track = search_result["tracks"][0]
            track_id = track.id

            if track.name.lower() in existing_tracks:
                print(f"❌ '{track.name}' is already in playlist '{playlist.name}', skipping...")
            else:
                playlist.add([track_id])
                print(f"🎵 Added '{track.name}' by '{track.artist.name}' to '{playlist.name}'")
        else:
            print(f"❌ Track '{track_name}' by '{artist_name}' not found.")
            not_found_tracks.append({"Playlist Name": playlist_name, "Track Name": track_name, "Artist Name": artist_name})

    # Save tracks that weren't found
    if not_found_tracks:
        pd.DataFrame(not_found_tracks).to_csv(NOT_FOUND_FILE, index=False)
        print(f"📁 Saved missing tracks to '{NOT_FOUND_FILE}'.")
    else:
        print("✅ All songs added successfully!")

# Run script
session = authenticate()
user = session.user
if session.check_login():
    song_data = load_library()
    add_songs_to_playlists(session, user, song_data)
else:
    print("❌ Authentication failed.")
