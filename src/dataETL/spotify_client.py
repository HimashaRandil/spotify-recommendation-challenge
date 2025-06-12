#!/usr/bin/env python3
"""
Spotify API client with corrected endpoints and authentication
"""

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.exceptions import SpotifyException
import time
import json
from typing import List, Dict, Optional
import os
from tqdm import tqdm

from src.utils.logger.logging import logger as logging


class SpotifyAudioFeatureCollector:
    """
    Collect audio features using correct Spotify API endpoints
    """

    def __init__(self, client_id: str, client_secret: str):
        """Initialize with proper Client Credentials flow"""

        try:
            # Validate input
            if not client_id or not client_secret:
                raise ValueError("Client ID and Client Secret are required")

            # Use Client Credentials Manager (no user auth needed)
            auth_manager = SpotifyClientCredentials(
                client_id=client_id, client_secret=client_secret
            )

            # Initialize Spotify client
            self.sp = spotipy.Spotify(
                auth_manager=auth_manager,  # Use auth_manager instead of client_credentials_manager
                requests_timeout=30,
                retries=2,
            )

            # Test the connection
            self._test_connection()

            logging.success("✅ Spotify API client initialized successfully")

        except Exception as e:
            logging.error(f"Failed to initialize Spotify client: {e}")
            raise

    def _test_connection(self):
        """Test API connection with a simple call"""
        try:
            # Test with a simple search (no OAuth required)
            test_results = self.sp.search(q="test", type="track", limit=1)

            if not test_results or not test_results.get("tracks", {}).get("items"):
                raise Exception("API test failed - no results returned")

            # Test audio features with a known track
            test_track_id = "4uLU6hMCjMI75M1A2tKUQC"  # Known good track ID
            audio_features = self.sp.audio_features([test_track_id])

            if not audio_features or not audio_features[0]:
                raise Exception("Audio features test failed")

            logging.info("✅ API connection and audio features test passed")

        except SpotifyException as e:
            if e.http_status == 401:
                logging.error("❌ 401 Unauthorized: Invalid Client ID or Client Secret")
            elif e.http_status == 403:
                logging.error("❌ 403 Forbidden: App may not have proper permissions")
                logging.error(
                    "   Check your app settings in Spotify Developer Dashboard"
                )
            else:
                logging.error(f"❌ Spotify API Error {e.http_status}: {e}")
            raise
        except Exception as e:
            logging.error(f"❌ Connection test failed: {e}")
            raise

    def extract_track_id_from_uri(self, track_uri: str) -> str:
        """Extract track ID from Spotify URI"""
        if track_uri.startswith("spotify:track:"):
            return track_uri.split(":")[-1]
        else:
            return track_uri  # Assume it's already an ID

    def get_audio_features_batch(
        self, track_uris: List[str]
    ) -> Dict[str, Optional[Dict]]:
        """Get audio features for a batch of tracks"""

        if not track_uris:
            return {}

        # Limit batch size to 100 (Spotify's limit)
        if len(track_uris) > 100:
            track_uris = track_uris[:100]

        # Extract track IDs
        track_ids = [self.extract_track_id_from_uri(uri) for uri in track_uris]

        try:
            # Call Spotify API (spotipy handles the correct endpoint)
            features_list = self.sp.audio_features(track_ids)

            # Map results back to URIs
            result = {}
            for i, features in enumerate(features_list):
                track_uri = track_uris[i]

                if features:  # Features found
                    result[track_uri] = {
                        "acousticness": features["acousticness"],
                        "danceability": features["danceability"],
                        "energy": features["energy"],
                        "instrumentalness": features["instrumentalness"],
                        "liveness": features["liveness"],
                        "loudness": features["loudness"],
                        "speechiness": features["speechiness"],
                        "tempo": features["tempo"],
                        "valence": features["valence"],
                        "key": features["key"],
                        "mode": features["mode"],
                        "time_signature": features["time_signature"],
                    }
                else:  # No features available for this track
                    result[track_uri] = None

            return result

        except SpotifyException as e:
            if e.http_status == 429:  # Rate limited
                retry_after = int(e.headers.get("Retry-After", 60))
                logging.warning(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                return {}  # Return empty, let caller retry
            else:
                logging.error(f"Spotify API error {e.http_status}: {e}")
                return {}
        except Exception as e:
            logging.error(f"Unexpected error getting audio features: {e}")
            return {}

    def collect_all_audio_features(
        self,
        track_uris: List[str],
        output_file: str,
        batch_size: int = 50,
        delay: float = 1.0,
    ) -> Dict[str, Optional[Dict]]:
        """Collect audio features for all tracks with conservative rate limiting"""

        logging.info(f"🎵 Collecting audio features for {len(track_uris):,} tracks")
        logging.info(f"📦 Using batch size: {batch_size}, delay: {delay}s")

        all_features = {}
        failed_tracks = []
        successful_batches = 0

        # Process in batches
        total_batches = (len(track_uris) + batch_size - 1) // batch_size

        for i in tqdm(
            range(0, len(track_uris), batch_size), desc="Collecting features"
        ):
            batch = track_uris[i : i + batch_size]
            batch_num = (i // batch_size) + 1

            try:
                # Get features for this batch
                batch_features = self.get_audio_features_batch(batch)

                if batch_features:  # If we got some results
                    all_features.update(batch_features)
                    successful_batches += 1

                    # Track failures within this batch
                    for uri in batch:
                        if uri not in batch_features or batch_features[uri] is None:
                            failed_tracks.append(uri)
                else:
                    # Entire batch failed
                    failed_tracks.extend(batch)
                    logging.warning(f"Batch {batch_num}/{total_batches} failed")

                # Conservative rate limiting
                time.sleep(delay)

                # Save progress periodically
                if batch_num % 10 == 0:
                    self.save_features_to_file(all_features, output_file + ".tmp")
                    success_count = len(
                        [f for f in all_features.values() if f is not None]
                    )
                    logging.info(
                        f"Progress: {success_count:,} features collected ({batch_num}/{total_batches} batches)"
                    )

            except Exception as e:
                logging.error(f"Error processing batch {batch_num}: {e}")
                failed_tracks.extend(batch)
                time.sleep(5)  # Longer delay on error

        # Final save
        self.save_features_to_file(all_features, output_file)

        # Calculate final statistics
        success_count = len([f for f in all_features.values() if f is not None])

        logging.info("📊 Final Collection Summary:")
        logging.info(f"   Total tracks requested: {len(track_uris):,}")
        logging.info(f"   Features collected: {success_count:,}")
        logging.info(f"   Failed/Missing: {len(failed_tracks):,}")
        logging.info(f"   Success rate: {success_count/len(track_uris)*100:.1f}%")
        logging.info(f"   Successful batches: {successful_batches}/{total_batches}")

        if failed_tracks:
            failed_file = output_file + ".failed"
            with open(failed_file, "w") as f:
                json.dump(failed_tracks, f, indent=2)
            logging.info(f"Failed tracks saved to: {failed_file}")

        return all_features

    def save_features_to_file(self, features: Dict, filename: str):
        """Save audio features to JSON file"""
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(features, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logging.error(f"Failed to save features: {e}")
