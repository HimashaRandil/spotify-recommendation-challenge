#!/usr/bin/env python3
"""
Extended Spotify API endpoint testing
"""

import os
from dotenv import load_dotenv
import requests
import base64


def test_multiple_endpoints():
    """Test multiple Spotify endpoints to isolate the issue"""

    load_dotenv()

    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

    print("🔐 Extended Spotify API Testing")
    print("=" * 50)

    # --- Correct Spotify Token URL ---
    token_url = "https://accounts.spotify.com/api/token"

    # Get access token
    credentials = f"{client_id}:{client_secret}"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()

    headers = {
        "Authorization": f"Basic {encoded_credentials}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {"grant_type": "client_credentials"}

    print("Attempting to get access token...")
    try:
        response = requests.post(token_url, headers=headers, data=data)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

        access_token = response.json()["access_token"]
        print("✅ Access token obtained successfully!")
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to get access token: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"    Status Code: {e.response.status_code}")
            print(f"    Response Body: {e.response.text}")
        return

    api_headers = {"Authorization": f"Bearer {access_token}"}

    # --- Define the Spotify API base URL ---
    SPOTIFY_API_BASE_URL = "https://api.spotify.com/v1"

    # --- Sample Track IDs ---
    SAMPLE_TRACK_ID_RICK = (
        "2takcwOaAZWiXQijPHIx7B"  # Rick Astley - Never Gonna Give You Up
    )
    SAMPLE_TRACK_ID_ADELE = "6UoF0fCJzE0b1oM3C5r30J"  # Adele - Hello
    SAMPLE_TRACK_ID_DOCS = "11dFghVXANMlKmJXsNCbNl"  # Example from Spotify docs

    # Test different endpoints
    endpoints_to_test = [
        {
            "name": "Search Tracks (Hello by Adele)",
            "url": f"{SPOTIFY_API_BASE_URL}/search?q=hello&type=track&limit=1",
            "expected": "Should work for all apps",
        },
        {
            "name": "Get Track Info (Never Gonna Give You Up)",
            "url": f"{SPOTIFY_API_BASE_URL}/tracks/{SAMPLE_TRACK_ID_RICK}",
            "expected": "Should work for all apps",
        },
        {
            "name": "Audio Features (Single) - Never Gonna Give You Up",
            "url": f"{SPOTIFY_API_BASE_URL}/audio-features/{SAMPLE_TRACK_ID_RICK}",
            "expected": "May require special permissions",
        },
        {
            "name": "Audio Features (Single) - Adele Hello",
            "url": f"{SPOTIFY_API_BASE_URL}/audio-features/{SAMPLE_TRACK_ID_ADELE}",
            "expected": "May require special permissions",
        },
        {
            "name": "Audio Features (Batch)",
            "url": f"{SPOTIFY_API_BASE_URL}/audio-features?ids={SAMPLE_TRACK_ID_RICK},{SAMPLE_TRACK_ID_ADELE}",
            "expected": "May require special permissions",
        },
    ]

    print(f"\n🧪 Testing {len(endpoints_to_test)} endpoints...")
    print("-" * 60)

    for endpoint in endpoints_to_test:
        print(f"\n📡 Testing: {endpoint['name']}")
        print(f"   URL: {endpoint['url']}")
        print(f"   Expected: {endpoint['expected']}")

        try:
            response = requests.get(endpoint["url"], headers=api_headers)

            if response.status_code == 200:
                print(f"   ✅ Status: {response.status_code} - SUCCESS")

                # Show sample data for successful calls
                data = response.json()
                if "tracks" in data and "items" in data["tracks"]:
                    # Search Tracks response
                    if data["tracks"]["items"]:
                        track = data["tracks"]["items"][0]
                        print(
                            f"   📊 Sample: {track.get('name', 'Unknown')} by {track.get('artists', [{}])[0].get('name', 'Unknown')}"
                        )
                    else:
                        print("   📊 No tracks found in search results.")
                elif "name" in data and "artists" in data:
                    # Get Track Info response
                    print(
                        f"   📊 Track: {data['name']} by {data['artists'][0]['name']}"
                    )
                elif "danceability" in data and "energy" in data:
                    # Audio Features (Single) response
                    print(
                        f"   📊 Audio Features: danceability={data['danceability']:.3f}, energy={data['energy']:.3f}"
                    )
                elif "audio_features" in data and isinstance(
                    data["audio_features"], list
                ):
                    # Audio Features (Batch) response
                    if data["audio_features"]:
                        first_feature = data["audio_features"][0]
                        print(
                            f"   📊 Audio Features (Batch - first track): danceability={first_feature.get('danceability', 0.0):.3f}, energy={first_feature.get('energy', 0.0):.3f}"
                        )
                    else:
                        print("   📊 No audio features found in batch response.")
                else:
                    print(f"   📊 Unknown response format: {data}")

            else:
                print(f"   ❌ Status: {response.status_code} - FAILED")
                try:
                    error_data = response.json()
                    if "error" in error_data:
                        print(f"   💬 Error: {error_data['error']}")
                    else:
                        print(f"   💬 Response (JSON): {error_data}")
                except requests.exceptions.JSONDecodeError:
                    print(
                        f"   💬 Response (Text): {response.text[:200]}..."
                    )  # Show more of the response text

        except requests.exceptions.ConnectionError:
            print(f"   ❌ Connection Error: Could not connect to {endpoint['url']}")
        except requests.exceptions.Timeout:
            print(f"   ❌ Timeout Error: Request to {endpoint['url']} timed out.")
        except requests.exceptions.HTTPError as e:
            print(f"   ❌ HTTP Error: {e}")
            if hasattr(e, "response") and e.response is not None:
                print(f"    Status Code: {e.response.status_code}")
                print(f"    Response Body: {e.response.text}")
        except Exception as e:
            print(f"   ❌ An unexpected Exception occurred: {e}")

    print("\n" + "=" * 60)
    print("📋 DIAGNOSIS:")

    print("\nIf Search and Track Info work but Audio Features fail:")
    print("   → Your app needs special permissions for audio features")
    print(
        "   → Add your email to 'Users and access' in Spotify Dashboard (for your new app)"
    )

    print("\nIf everything fails (including access token):")
    print("   → General app configuration issue or incorrect Client ID/Secret.")
    print("   → Double-check app status and settings in Spotify Dashboard.")
    print("   → Ensure your .env file is correctly loaded and values are accurate.")


if __name__ == "__main__":
    test_multiple_endpoints()
