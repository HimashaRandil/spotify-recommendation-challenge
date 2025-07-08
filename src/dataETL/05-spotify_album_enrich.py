#!/usr/bin/env python3
"""
Enrich album data with Spotify Web API information - WITH RESUME FUNCTIONALITY
"""

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.exceptions import SpotifyException
import time
import json
import os
from typing import Dict, List, Optional
from tqdm import tqdm
import tempfile
import shutil

from src.utils.logger.logging import logger as logging


class SpotifyAlbumEnricher:
    """
    Enrich album data using Spotify Web API
    """

    def __init__(self, client_id: str, client_secret: str):
        """Initialize Spotify client with Client Credentials flow"""

        # Clear any cached credential files
        try:
            cache_paths = [
                os.path.expanduser("~/.cache"),
                os.path.expanduser("~/.spotipy_cache"),
                tempfile.gettempdir() + "/spotipy",
            ]
            for path in cache_paths:
                if os.path.exists(path):
                    shutil.rmtree(path, ignore_errors=True)
        except Exception:
            pass

        try:
            # Validate credentials
            if not client_id or not client_secret:
                raise ValueError("Client ID and Client Secret are required")

            # Initialize Spotify client
            auth_manager = SpotifyClientCredentials(
                client_id=client_id, client_secret=client_secret
            )

            self.sp = spotipy.Spotify(
                auth_manager=auth_manager, requests_timeout=30, retries=3
            )

            # Test connection
            self._test_connection()
            logging.success("✅ Spotify API client initialized successfully")

        except Exception as e:
            logging.error(f"❌ Failed to initialize Spotify client: {e}")
            raise

    def _test_connection(self):
        """Test API connection"""
        try:
            # Test with a known album ID
            test_album_id = "4aawyAB9vmqN3uQ7FjRGTy"  # Global Citizen EP 1
            album_info = self.sp.album(test_album_id)

            if not album_info or not album_info.get("name"):
                raise Exception("API test failed - no album data returned")

            logging.info(f"✅ API test passed - Retrieved: {album_info['name']}")

        except SpotifyException as e:
            if e.http_status == 401:
                logging.error("❌ 401 Unauthorized: Invalid credentials")
            elif e.http_status == 403:
                logging.error("❌ 403 Forbidden: Check app permissions")
            else:
                logging.error(f"❌ Spotify API Error {e.http_status}: {e}")
            raise
        except Exception as e:
            logging.error(f"❌ Connection test failed: {e}")
            raise

    def _extract_id_from_uri(self, uri: str) -> str:
        """Extract Spotify ID from URI"""
        return uri.split(":")[-1] if uri.startswith("spotify:album:") else uri

    def get_album_info(self, album_id: str) -> Optional[Dict]:
        """Get detailed album information from Spotify API"""

        try:
            album_data = self.sp.album(album_id)

            if not album_data:
                return None

            # Extract relevant information
            enriched_data = {
                "spotify_id": album_data["id"],
                "name": album_data["name"],
                "album_type": album_data.get(
                    "album_type", ""
                ),  # album, single, compilation
                "total_tracks": album_data.get("total_tracks", 0),
                "release_date": album_data.get("release_date", ""),
                "popularity": album_data.get("popularity", 0),
                "genres": album_data.get("genres", []),
                "label": album_data.get("label", ""),
                "artists": [
                    {"id": artist["id"], "name": artist["name"], "uri": artist["uri"]}
                    for artist in album_data.get("artists", [])
                ],
                "external_urls": album_data.get("external_urls", {}),
                "uri": album_data["uri"],  # Just count, not full list
            }

            return enriched_data

        except SpotifyException as e:
            if e.http_status == 404:
                logging.warning(f"Album not found: {album_id}")
                return None
            elif e.http_status == 429:
                # Rate limited
                retry_after = int(e.headers.get("Retry-After", 60))
                logging.warning(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                return None  # Let caller retry
            else:
                logging.error(f"API error for album {album_id}: {e}")
                return None
        except Exception as e:
            logging.error(f"Unexpected error for album {album_id}: {e}")
            return None

    def get_albums_batch(self, album_ids: List[str]) -> Dict[str, Optional[Dict]]:
        """Get album information for a batch of albums (up to 20)"""

        if not album_ids:
            return {}

        # Spotify API supports up to 20 albums per request (different from artists)
        if len(album_ids) > 20:
            album_ids = album_ids[:20]

        try:
            albums_data = self.sp.albums(album_ids)

            if not albums_data or not albums_data.get("albums"):
                return {}

            result = {}
            for album_data in albums_data["albums"]:
                if album_data:  # Album found
                    enriched_data = {
                        "spotify_id": album_data["id"],
                        "name": album_data["name"],
                        "album_type": album_data.get("album_type", ""),
                        "total_tracks": album_data.get("total_tracks", 0),
                        "release_date": album_data.get("release_date", ""),
                        "popularity": album_data.get("popularity", 0),
                        "genres": album_data.get("genres", []),
                        "label": album_data.get("label", ""),
                        "artists": [
                            {
                                "id": artist["id"],
                                "name": artist["name"],
                                "uri": artist["uri"],
                            }
                            for artist in album_data.get("artists", [])
                        ],
                        "external_urls": album_data.get("external_urls", {}),
                        "uri": album_data["uri"],
                    }
                    result[album_data["id"]] = enriched_data

            return result

        except SpotifyException as e:
            if e.http_status == 429:
                retry_after = int(e.headers.get("Retry-After", 60))
                logging.warning(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                return {}
            else:
                logging.error(f"Batch API error: {e}")
                return {}
        except Exception as e:
            logging.error(f"Unexpected batch error: {e}")
            return {}

    def enrich_albums_from_file(
        self,
        input_file: str,
        output_file: str,
        batch_size: int = 20,  # Conservative batch size (max 20 for albums)
        delay: float = 1.0,  # Conservative delay
        max_albums: Optional[int] = None,
        testing_mode: bool = False,
    ) -> Dict[str, Dict]:
        """Enrich albums from interim file and save to processed folder - WITH RESUME"""

        logging.info(f"🔍 Loading albums from: {input_file}")

        # Load original album data
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        all_albums = data["albums"]

        # ===== RESUME LOGIC - Check for existing progress =====
        existing_enriched = {}
        progress_file = output_file + ".tmp"

        if os.path.exists(progress_file):
            logging.info(f"📂 Found existing progress file: {progress_file}")
            try:
                with open(progress_file, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)

                # Build lookup of already enriched albums
                for album in existing_data.get("albums", []):
                    album_id = self._extract_id_from_uri(album["album_uri"])
                    existing_enriched[album_id] = album

                logging.info(
                    f"📊 Found {len(existing_enriched):,} already enriched albums"
                )

            except Exception as e:
                logging.warning(f"⚠️  Could not load existing progress: {e}")
                existing_enriched = {}

        # Filter out albums that are already enriched
        def extract_id_from_uri(uri):
            return uri.split(":")[-1] if uri.startswith("spotify:album:") else uri

        albums_to_process = []
        for album in all_albums:
            album_id = extract_id_from_uri(album["album_uri"])
            if album_id not in existing_enriched:
                albums_to_process.append(album)

        logging.info(f"🎯 Total albums: {len(all_albums):,}")
        logging.info(f"✅ Already enriched: {len(existing_enriched):,}")
        logging.info(f"🔄 Remaining to process: {len(albums_to_process):,}")

        # Use existing enriched data as starting point
        enriched_albums = existing_enriched.copy()
        albums = albums_to_process

        # If no albums left to process, we're done!
        if not albums:
            logging.success("🎉 All albums already enriched! Nothing to do.")
            return enriched_albums

        # Testing mode - process only top frequent albums for testing
        if testing_mode:
            # Get top 5 albums for testing
            test_albums = albums[:5]
            logging.info(f"🧪 TESTING MODE: Processing top {len(test_albums)} albums")
            for i, album in enumerate(test_albums, 1):
                logging.info(
                    f"   {i}. {album['album_name']} by {album['artist_name']} ({album['album_uri']})"
                )
            albums = test_albums
        elif max_albums:
            albums = albums[:max_albums]
            logging.info(f"🧪 Processing first {len(albums)} albums for testing")

        logging.info(f"💿 Enriching {len(albums):,} NEW albums with Spotify data")
        logging.info(f"📦 Using batch size: {batch_size}, delay: {delay}s")

        failed_albums = []
        successful_requests = 0

        # Extract album IDs (from URI)
        album_ids = [extract_id_from_uri(album["album_uri"]) for album in albums]
        album_lookup = {
            extract_id_from_uri(album["album_uri"]): album for album in albums
        }

        # Process in batches
        total_batches = (len(album_ids) + batch_size - 1) // batch_size

        for i in tqdm(range(0, len(album_ids), batch_size), desc="Enriching albums"):
            batch_ids = album_ids[i : i + batch_size]
            batch_num = (i // batch_size) + 1

            try:
                # Get enriched data for batch
                batch_results = self.get_albums_batch(batch_ids)

                if batch_results:
                    successful_requests += 1

                    # Merge original data with enriched data
                    for album_id, enriched_data in batch_results.items():
                        if album_id in album_lookup:
                            original_data = album_lookup[album_id]

                            # Combine original MPD data with Spotify API data
                            combined_data = {
                                **original_data,  # Original data from MPD
                                "spotify_api_data": enriched_data,  # New data from API
                                "enrichment_status": "success",
                            }

                            enriched_albums[album_id] = combined_data

                    # Track failed albums in this batch
                    for album_id in batch_ids:
                        if album_id not in batch_results:
                            failed_albums.append(album_id)
                            # Still include original data but mark as failed
                            enriched_albums[album_id] = {
                                **album_lookup[album_id],
                                "spotify_api_data": None,
                                "enrichment_status": "failed",
                            }
                else:
                    # Entire batch failed
                    for album_id in batch_ids:
                        failed_albums.append(album_id)
                        enriched_albums[album_id] = {
                            **album_lookup[album_id],
                            "spotify_api_data": None,
                            "enrichment_status": "failed",
                        }
                    logging.warning(
                        f"Batch {batch_num}/{total_batches} failed completely"
                    )

                # Rate limiting
                time.sleep(delay)

                # Save progress periodically
                if batch_num % 10 == 0:
                    self._save_enriched_data(enriched_albums, output_file + ".tmp")
                    success_count = len(
                        [
                            a
                            for a in enriched_albums.values()
                            if a["enrichment_status"] == "success"
                        ]
                    )
                    logging.info(
                        f"Progress: {success_count:,} albums enriched ({batch_num}/{total_batches} batches)"
                    )

            except Exception as e:
                logging.error(f"Error processing batch {batch_num}: {e}")
                # Mark all albums in failed batch
                for album_id in batch_ids:
                    failed_albums.append(album_id)
                    enriched_albums[album_id] = {
                        **album_lookup[album_id],
                        "spotify_api_data": None,
                        "enrichment_status": "error",
                    }
                time.sleep(5)  # Longer delay on error

        # Final save
        self._save_enriched_data(enriched_albums, output_file)

        # Calculate statistics (including existing + new)
        all_enriched_count = len(enriched_albums)
        new_success_count = len(
            [
                a
                for album_id, a in enriched_albums.items()
                if album_id in [extract_id_from_uri(alb["album_uri"]) for alb in albums]
                and a.get("enrichment_status") == "success"
            ]
        )

        logging.info("📊 Final Enrichment Summary:")
        logging.info(f"   Total albums in dataset: {len(all_albums):,}")
        logging.info(f"   Previously enriched: {len(existing_enriched):,}")
        logging.info(f"   Processed this session: {len(albums):,}")
        logging.info(f"   Successfully enriched this session: {new_success_count:,}")
        logging.info(f"   Failed this session: {len(failed_albums):,}")
        logging.info(f"   Total enriched albums: {all_enriched_count:,}")
        if len(albums) > 0:
            logging.info(
                f"   Session success rate: {new_success_count/len(albums)*100:.1f}%"
            )

        return enriched_albums

    def _save_enriched_data(self, enriched_albums: Dict[str, Dict], output_file: str):
        """Save enriched album data to JSON file"""

        try:
            # Create output directory
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            # Prepare final data structure
            output_data = {
                "metadata": {
                    "enrichment_date": None,
                    "total_albums": len(enriched_albums),
                    "successfully_enriched": len(
                        [
                            a
                            for a in enriched_albums.values()
                            if a["enrichment_status"] == "success"
                        ]
                    ),
                    "description": "Albums enriched with Spotify Web API data",
                },
                "albums": list(enriched_albums.values()),
            }

            # Save to file
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            logging.success(f"✅ Saved enriched data to: {output_file}")

        except Exception as e:
            logging.error(f"❌ Failed to save enriched data: {e}")


def main():
    """Main execution function"""

    # Configuration
    CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
    CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

    INTERIM_INPUT_FILE = "data/interim/unique_albums.json"
    PROCESSED_OUTPUT_FILE = "data/processed/enriched_albums.json"

    # ===== CONFIGURATION FLAGS =====
    TESTING_MODE = False  # Set to True for testing with top 5 albums
    MAX_ALBUMS_FOR_TESTING = None  # Alternative: set number like 10

    try:
        # Validate environment variables
        if not CLIENT_ID or not CLIENT_SECRET:
            raise ValueError(
                "Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables"
            )

        # Initialize enricher
        enricher = SpotifyAlbumEnricher(CLIENT_ID, CLIENT_SECRET)

        # Enrich albums
        enriched_data = enricher.enrich_albums_from_file(
            input_file=INTERIM_INPUT_FILE,
            output_file=PROCESSED_OUTPUT_FILE,
            testing_mode=TESTING_MODE,
            max_albums=MAX_ALBUMS_FOR_TESTING,
        )

        logging.success("🎉 Album enrichment completed successfully!")

        # Show sample enriched data for testing
        if TESTING_MODE and enriched_data:
            logging.info("📋 Sample enriched data:")
            sample_album = next(iter(enriched_data.values()))
            if sample_album.get("spotify_api_data"):
                api_data = sample_album["spotify_api_data"]
                logging.info(f"   Album: {sample_album['album_name']}")
                logging.info(f"   Artist: {sample_album['artist_name']}")
                logging.info(f"   Album Type: {api_data.get('album_type', 'N/A')}")
                logging.info(f"   Release Date: {api_data.get('release_date', 'N/A')}")
                logging.info(f"   Total Tracks: {api_data.get('total_tracks', 'N/A')}")
                logging.info(f"   Popularity: {api_data.get('popularity', 'N/A')}")
                logging.info(f"   Label: {api_data.get('label', 'N/A')}")

    except Exception as e:
        logging.error(f"❌ Album enrichment failed: {e}")
        raise


if __name__ == "__main__":
    main()
