#!/usr/bin/env python3
"""
Enrich artist data with Spotify Web API information - WITH RESUME FUNCTIONALITY
"""

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from spotipy.exceptions import SpotifyException
import time
import json
import os
from typing import Dict, List, Optional
from tqdm import tqdm

from src.utils.logger.logging import logger as logging


class SpotifyArtistEnricher:
    """
    Enrich artist data using Spotify Web API
    """

    def __init__(self, client_id: str, client_secret: str):
        """Initialize Spotify client with Client Credentials flow"""

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
            # Test with a known artist ID
            test_artist_id = "4Z8W4fKeB5YxbusRsdQVPb"  # Radiohead
            artist_info = self.sp.artist(test_artist_id)

            if not artist_info or not artist_info.get("name"):
                raise Exception("API test failed - no artist data returned")

            logging.info(f"✅ API test passed - Retrieved: {artist_info['name']}")

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
        return uri.split(":")[-1] if uri.startswith("spotify:artist:") else uri

    def get_artist_info(self, artist_id: str) -> Optional[Dict]:
        """Get detailed artist information from Spotify API"""

        try:
            artist_data = self.sp.artist(artist_id)

            if not artist_data:
                return None

            # Extract relevant information
            enriched_data = {
                "spotify_id": artist_data["id"],
                "name": artist_data["name"],
                "popularity": artist_data.get("popularity", 0),
                "genres": artist_data.get("genres", []),
                "followers": artist_data.get("followers", {}).get("total", 0),
                "external_urls": artist_data.get("external_urls", {}),
                "images": artist_data.get("images", []),
                "uri": artist_data["uri"],
            }

            return enriched_data

        except SpotifyException as e:
            if e.http_status == 404:
                logging.warning(f"Artist not found: {artist_id}")
                return None
            elif e.http_status == 429:
                # Rate limited
                retry_after = int(e.headers.get("Retry-After", 60))
                logging.warning(f"Rate limited. Waiting {retry_after} seconds...")
                time.sleep(retry_after)
                return None  # Let caller retry
            else:
                logging.error(f"API error for artist {artist_id}: {e}")
                return None
        except Exception as e:
            logging.error(f"Unexpected error for artist {artist_id}: {e}")
            return None

    def get_artists_batch(self, artist_ids: List[str]) -> Dict[str, Optional[Dict]]:
        """Get artist information for a batch of artists (up to 50)"""

        if not artist_ids:
            return {}

        # Spotify API supports up to 50 artists per request
        if len(artist_ids) > 50:
            artist_ids = artist_ids[:50]

        try:
            artists_data = self.sp.artists(artist_ids)

            if not artists_data or not artists_data.get("artists"):
                return {}

            result = {}
            for artist_data in artists_data["artists"]:
                if artist_data:  # Artist found
                    enriched_data = {
                        "spotify_id": artist_data["id"],
                        "name": artist_data["name"],
                        "popularity": artist_data.get("popularity", 0),
                        "genres": artist_data.get("genres", []),
                        "followers": artist_data.get("followers", {}).get("total", 0),
                        "external_urls": artist_data.get("external_urls", {}),
                        "images": artist_data.get("images", []),
                        "uri": artist_data["uri"],
                    }
                    result[artist_data["id"]] = enriched_data
                else:
                    # Artist not found - we don't know which ID this corresponds to
                    # This is a limitation of the batch API
                    pass

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

    def enrich_artists_from_file(
        self,
        input_file: str,
        output_file: str,
        batch_size: int = 25,  # Conservative batch size
        delay: float = 1.0,  # Conservative delay
        max_artists: Optional[int] = None,
        testing_mode: bool = False,
    ) -> Dict[str, Dict]:
        """Enrich artists from interim file and save to processed folder - WITH RESUME"""

        logging.info(f"🔍 Loading artists from: {input_file}")

        # Load original artist data
        with open(input_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        all_artists = data["artists"]

        # ===== RESUME LOGIC - Check for existing progress =====
        existing_enriched = {}
        progress_file = output_file + ".tmp"

        if os.path.exists(progress_file):
            logging.info(f"📂 Found existing progress file: {progress_file}")
            try:
                with open(progress_file, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)

                # Build lookup of already enriched artists
                for artist in existing_data.get("artists", []):
                    artist_id = self._extract_id_from_uri(artist["artist_uri"])
                    existing_enriched[artist_id] = artist

                logging.info(
                    f"📊 Found {len(existing_enriched):,} already enriched artists"
                )

            except Exception as e:
                logging.warning(f"⚠️  Could not load existing progress: {e}")
                existing_enriched = {}

        # Filter out artists that are already enriched
        def extract_id_from_uri(uri):
            return uri.split(":")[-1] if uri.startswith("spotify:artist:") else uri

        artists_to_process = []
        for artist in all_artists:
            artist_id = extract_id_from_uri(artist["artist_uri"])
            if artist_id not in existing_enriched:
                artists_to_process.append(artist)

        logging.info(f"🎯 Total artists: {len(all_artists):,}")
        logging.info(f"✅ Already enriched: {len(existing_enriched):,}")
        logging.info(f"🔄 Remaining to process: {len(artists_to_process):,}")

        # Use existing enriched data as starting point
        enriched_artists = existing_enriched.copy()
        artists = artists_to_process

        # If no artists left to process, we're done!
        if not artists:
            logging.success("🎉 All artists already enriched! Nothing to do.")
            return enriched_artists

        # Testing mode - process only top frequent artists for testing
        if testing_mode:
            # Get top 5 artists for testing
            test_artists = artists[:5]
            logging.info(f"🧪 TESTING MODE: Processing top {len(test_artists)} artists")
            for i, artist in enumerate(test_artists, 1):
                logging.info(
                    f"   {i}. {artist['artist_name']} ({artist['artist_uri']})"
                )
            artists = test_artists
        elif max_artists:
            artists = artists[:max_artists]
            logging.info(f"🧪 Processing first {len(artists)} artists for testing")

        logging.info(f"🎤 Enriching {len(artists):,} NEW artists with Spotify data")
        logging.info(f"📦 Using batch size: {batch_size}, delay: {delay}s")

        failed_artists = []
        successful_requests = 0

        # Extract artist IDs (from URI)
        artist_ids = [extract_id_from_uri(artist["artist_uri"]) for artist in artists]
        artist_lookup = {
            extract_id_from_uri(artist["artist_uri"]): artist for artist in artists
        }

        # Process in batches
        total_batches = (len(artist_ids) + batch_size - 1) // batch_size

        for i in tqdm(range(0, len(artist_ids), batch_size), desc="Enriching artists"):
            batch_ids = artist_ids[i : i + batch_size]
            batch_num = (i // batch_size) + 1

            try:
                # Get enriched data for batch
                batch_results = self.get_artists_batch(batch_ids)

                if batch_results:
                    successful_requests += 1

                    # Merge original data with enriched data
                    for artist_id, enriched_data in batch_results.items():
                        if artist_id in artist_lookup:
                            original_data = artist_lookup[artist_id]

                            # Combine original MPD data with Spotify API data
                            combined_data = {
                                **original_data,  # Original data from MPD
                                "spotify_api_data": enriched_data,  # New data from API
                                "enrichment_status": "success",
                            }

                            enriched_artists[artist_id] = combined_data

                    # Track failed artists in this batch
                    for artist_id in batch_ids:
                        if artist_id not in batch_results:
                            failed_artists.append(artist_id)
                            # Still include original data but mark as failed
                            enriched_artists[artist_id] = {
                                **artist_lookup[artist_id],
                                "spotify_api_data": None,
                                "enrichment_status": "failed",
                            }
                else:
                    # Entire batch failed
                    for artist_id in batch_ids:
                        failed_artists.append(artist_id)
                        enriched_artists[artist_id] = {
                            **artist_lookup[artist_id],
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
                    self._save_enriched_data(enriched_artists, output_file + ".tmp")
                    success_count = len(
                        [
                            a
                            for a in enriched_artists.values()
                            if a["enrichment_status"] == "success"
                        ]
                    )
                    logging.info(
                        f"Progress: {success_count:,} artists enriched ({batch_num}/{total_batches} batches)"
                    )

            except Exception as e:
                logging.error(f"Error processing batch {batch_num}: {e}")
                # Mark all artists in failed batch
                for artist_id in batch_ids:
                    failed_artists.append(artist_id)
                    enriched_artists[artist_id] = {
                        **artist_lookup[artist_id],
                        "spotify_api_data": None,
                        "enrichment_status": "error",
                    }
                time.sleep(5)  # Longer delay on error

        # Final save
        self._save_enriched_data(enriched_artists, output_file)

        # Calculate statistics (including existing + new)
        all_enriched_count = len(enriched_artists)
        new_success_count = len(
            [
                a
                for artist_id, a in enriched_artists.items()
                if artist_id
                in [extract_id_from_uri(art["artist_uri"]) for art in artists]
                and a.get("enrichment_status") == "success"
            ]
        )

        logging.info("📊 Final Enrichment Summary:")
        logging.info(f"   Total artists in dataset: {len(all_artists):,}")
        logging.info(f"   Previously enriched: {len(existing_enriched):,}")
        logging.info(f"   Processed this session: {len(artists):,}")
        logging.info(f"   Successfully enriched this session: {new_success_count:,}")
        logging.info(f"   Failed this session: {len(failed_artists):,}")
        logging.info(f"   Total enriched artists: {all_enriched_count:,}")
        if len(artists) > 0:
            logging.info(
                f"   Session success rate: {new_success_count/len(artists)*100:.1f}%"
            )

        return enriched_artists

    def _save_enriched_data(self, enriched_artists: Dict[str, Dict], output_file: str):
        """Save enriched artist data to JSON file"""

        try:
            # Create output directory
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            # Prepare final data structure
            output_data = {
                "metadata": {
                    "enrichment_date": None,  # Could add timestamp
                    "total_artists": len(enriched_artists),
                    "successfully_enriched": len(
                        [
                            a
                            for a in enriched_artists.values()
                            if a["enrichment_status"] == "success"
                        ]
                    ),
                    "description": "Artists enriched with Spotify Web API data",
                },
                "artists": list(enriched_artists.values()),
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

    INTERIM_INPUT_FILE = "data/interim/unique_artists.json"
    PROCESSED_OUTPUT_FILE = "data/processed/enriched_artists.json"

    # ===== CONFIGURATION FLAGS =====
    TESTING_MODE = False  # Set to True for testing with top 5 artists
    MAX_ARTISTS_FOR_TESTING = None  # Alternative: set number like 10

    try:
        # Validate environment variables
        if not CLIENT_ID or not CLIENT_SECRET:
            raise ValueError(
                "Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables"
            )

        # Initialize enricher
        enricher = SpotifyArtistEnricher(CLIENT_ID, CLIENT_SECRET)

        # Enrich artists
        enriched_data = enricher.enrich_artists_from_file(
            input_file=INTERIM_INPUT_FILE,
            output_file=PROCESSED_OUTPUT_FILE,
            testing_mode=TESTING_MODE,
            max_artists=MAX_ARTISTS_FOR_TESTING,
        )

        logging.success("🎉 Artist enrichment completed successfully!")

        # Show sample enriched data for testing
        if TESTING_MODE and enriched_data:
            logging.info("📋 Sample enriched data:")
            sample_artist = next(iter(enriched_data.values()))
            if sample_artist.get("spotify_api_data"):
                api_data = sample_artist["spotify_api_data"]
                logging.info(f"   Artist: {sample_artist['artist_name']}")
                logging.info(f"   Popularity: {api_data.get('popularity', 'N/A')}")
                logging.info(f"   Genres: {api_data.get('genres', [])}")
                logging.info(f"   Followers: {api_data.get('followers', 0):,}")

    except Exception as e:
        logging.error(f"❌ Artist enrichment failed: {e}")
        raise


if __name__ == "__main__":
    main()
