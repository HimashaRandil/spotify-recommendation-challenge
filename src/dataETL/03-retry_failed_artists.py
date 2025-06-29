#!/usr/bin/env python3
"""
Retry failed artist enrichments from previous run
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


class FailedArtistRetry:
    """
    Retry failed artist enrichments
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

    def analyze_failed_artists(self, enriched_file: str) -> Dict:
        """Analyze the enriched file to find failed artists"""

        logging.info(f"🔍 Analyzing failed artists from: {enriched_file}")

        try:
            with open(enriched_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            artists = data.get("artists", [])

            # Categorize artists by status
            successful = []
            failed = []
            error = []

            for artist in artists:
                status = artist.get("enrichment_status", "unknown")
                if status == "success":
                    successful.append(artist)
                elif status == "failed":
                    failed.append(artist)
                elif status == "error":
                    error.append(artist)

            # Report statistics
            logging.info("📊 Current Status Analysis:")
            logging.info(f"   Total artists: {len(artists):,}")
            logging.info(f"   ✅ Successful: {len(successful):,}")
            logging.info(f"   ❌ Failed: {len(failed):,}")
            logging.info(f"   💥 Error: {len(error):,}")

            # Show some examples of failed artists
            if failed:
                logging.info("\n🔍 Sample Failed Artists:")
                for i, artist in enumerate(failed[:5], 1):
                    logging.info(
                        f"   {i}. {artist['artist_name']} ({artist['artist_uri']})"
                    )
                if len(failed) > 5:
                    logging.info(f"   ... and {len(failed)-5:,} more")

            return {
                "total": len(artists),
                "successful": successful,
                "failed": failed,
                "error": error,
                "all_artists": artists,
            }

        except Exception as e:
            logging.error(f"❌ Error analyzing file: {e}")
            raise

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

    def retry_failed_artists(
        self,
        enriched_file: str,
        output_file: str,
        batch_size: int = 25,
        delay: float = 2.0,  # Slightly longer delay for retries
        max_retries: Optional[int] = None,
    ) -> Dict:
        """Retry failed artists and update the enriched file"""

        # Analyze current status
        analysis = self.analyze_failed_artists(enriched_file)
        failed_artists = analysis["failed"]
        error_artists = analysis["error"]

        # Combine failed and error artists for retry
        retry_candidates = failed_artists + error_artists

        if not retry_candidates:
            logging.success(
                "🎉 No failed artists to retry! All enrichments successful."
            )
            return analysis

        if max_retries:
            retry_candidates = retry_candidates[:max_retries]
            logging.info(
                f"🧪 TESTING: Only retrying first {len(retry_candidates)} failed artists"
            )

        logging.info(f"🔄 Retrying {len(retry_candidates):,} failed artists")
        logging.info(f"📦 Using batch size: {batch_size}, delay: {delay}s")

        # Start with all existing data
        all_artists_dict = {}
        for artist in analysis["all_artists"]:
            artist_id = self._extract_id_from_uri(artist["artist_uri"])
            all_artists_dict[artist_id] = artist

        retry_success_count = 0
        still_failed_count = 0

        # Process retry candidates in batches
        def extract_id_from_uri(uri):
            return uri.split(":")[-1] if uri.startswith("spotify:artist:") else uri

        artist_ids = [
            extract_id_from_uri(artist["artist_uri"]) for artist in retry_candidates
        ]
        artist_lookup = {
            extract_id_from_uri(artist["artist_uri"]): artist
            for artist in retry_candidates
        }

        total_batches = (len(artist_ids) + batch_size - 1) // batch_size

        for i in tqdm(
            range(0, len(artist_ids), batch_size), desc="Retrying failed artists"
        ):
            batch_ids = artist_ids[i : i + batch_size]
            batch_num = (i // batch_size) + 1

            try:
                # Get enriched data for batch
                batch_results = self.get_artists_batch(batch_ids)

                for artist_id in batch_ids:
                    if artist_id in batch_results:
                        # Success! Update the artist data
                        original_data = artist_lookup[artist_id]

                        updated_data = {
                            **original_data,
                            "spotify_api_data": batch_results[artist_id],
                            "enrichment_status": "success",
                        }

                        all_artists_dict[artist_id] = updated_data
                        retry_success_count += 1

                        logging.info(
                            f"✅ Retry success: {original_data['artist_name']}"
                        )

                    else:
                        # Still failed
                        original_data = artist_lookup[artist_id]

                        # Keep as failed but mark as retried
                        updated_data = {
                            **original_data,
                            "spotify_api_data": None,
                            "enrichment_status": "failed_retry",
                        }

                        all_artists_dict[artist_id] = updated_data
                        still_failed_count += 1

                # Rate limiting between batches
                time.sleep(delay)

                # Progress update
                if batch_num % 5 == 0:
                    logging.info(
                        f"Retry progress: {retry_success_count} successes, {still_failed_count} still failed ({batch_num}/{total_batches} batches)"
                    )

            except Exception as e:
                logging.error(f"Error processing retry batch {batch_num}: {e}")
                time.sleep(5)
                continue

        # Save updated results
        self._save_updated_data(all_artists_dict, output_file)

        # Final statistics
        logging.info("📊 Retry Results:")
        logging.info(f"   Artists retried: {len(retry_candidates):,}")
        logging.info(f"   ✅ Newly successful: {retry_success_count:,}")
        logging.info(f"   ❌ Still failed: {still_failed_count:,}")
        logging.info(
            f"   🎯 Retry success rate: {retry_success_count/len(retry_candidates)*100:.1f}%"
        )

        # Updated totals
        total_successful = len(analysis["successful"]) + retry_success_count
        total_failed = len(retry_candidates) - retry_success_count

        logging.info("\n📈 Updated Overall Statistics:")
        logging.info(f"   Total artists: {analysis['total']:,}")
        logging.info(f"   ✅ Total successful: {total_successful:,}")
        logging.info(f"   ❌ Total failed: {total_failed:,}")
        logging.info(
            f"   🎯 Overall success rate: {total_successful/analysis['total']*100:.1f}%"
        )

        return {
            "retry_attempted": len(retry_candidates),
            "retry_successful": retry_success_count,
            "still_failed": still_failed_count,
            "total_successful": total_successful,
            "total_failed": total_failed,
        }

    def _save_updated_data(self, artists_dict: Dict[str, Dict], output_file: str):
        """Save updated artist data to JSON file"""

        try:
            # Create output directory
            os.makedirs(os.path.dirname(output_file), exist_ok=True)

            # Convert dict back to list
            artists_list = list(artists_dict.values())

            # Prepare final data structure
            output_data = {
                "metadata": {
                    "enrichment_date": None,
                    "total_artists": len(artists_list),
                    "successfully_enriched": len(
                        [
                            a
                            for a in artists_list
                            if a.get("enrichment_status") == "success"
                        ]
                    ),
                    "description": "Artists enriched with Spotify Web API data (including retries)",
                },
                "artists": artists_list,
            }

            # Save to file
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)

            logging.success(f"✅ Updated data saved to: {output_file}")

        except Exception as e:
            logging.error(f"❌ Failed to save updated data: {e}")


def main():
    """Main execution function"""

    # Configuration
    CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
    CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")

    ENRICHED_INPUT_FILE = "data/processed/enriched_artists.json"  # Your completed file
    UPDATED_OUTPUT_FILE = (
        "data/processed/enriched_artists_updated.json"  # Updated file with retries
    )

    # ===== CONFIGURATION FLAGS =====
    TESTING_MODE = False  # Set to True to retry only first 50 failed artists
    MAX_RETRIES_FOR_TESTING = None  # Set to 50 for testing

    try:
        # Validate environment variables
        if not CLIENT_ID or not CLIENT_SECRET:
            raise ValueError(
                "Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables"
            )

        # Initialize retry handler
        retry_handler = FailedArtistRetry(CLIENT_ID, CLIENT_SECRET)

        # First, analyze the current state
        logging.info("🔍 Analyzing current enrichment state...")
        analysis = retry_handler.analyze_failed_artists(ENRICHED_INPUT_FILE)

        if analysis["failed"] or analysis["error"]:
            # Retry failed artists
            retry_handler.retry_failed_artists(
                enriched_file=ENRICHED_INPUT_FILE,
                output_file=UPDATED_OUTPUT_FILE,
                max_retries=MAX_RETRIES_FOR_TESTING if TESTING_MODE else None,
            )
        else:
            logging.success(
                "🎉 No failed artists found! All enrichments were successful."
            )

    except Exception as e:
        logging.error(f"❌ Retry process failed: {e}")
        raise


if __name__ == "__main__":
    main()
