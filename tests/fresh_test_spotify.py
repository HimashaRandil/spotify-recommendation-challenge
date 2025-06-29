import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# Hard-code your NEW credentials here
CLIENT_ID = "your client id here"
CLIENT_SECRET = "your client secret here"

print("Testing with fresh credentials...")

try:
    auth = SpotifyClientCredentials(client_id=CLIENT_ID, client_secret=CLIENT_SECRET)

    sp = spotipy.Spotify(auth_manager=auth)
    print("✅ Spotify client created")

    # Simple API test
    result = sp.search(q="drake", type="artist", limit=1)
    artist = result["artists"]["items"][0]
    print(f"✅ Success! Found: {artist['name']}")

except Exception as e:
    print(f"❌ Error: {e}")
