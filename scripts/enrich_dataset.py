#!/usr/bin/env python3
"""
Main script to enrich MPD dataset with Spotify audio features
"""

import os
from dotenv import load_dotenv  # Add this import

from src.dataETL.extractors import extract_unique_tracks_from_mpd, save_track_data
from src.dataETL.spotify_client import SpotifyAudioFeatureCollector
from src.utils.logger.logging import logger as logging


def main():
    """Main enrichment pipeline"""

    # Load environment variables from .env file
    load_dotenv()  # Add this line

    # Configuration
    DATA_DIR = "data/raw"
    INTERIM_DIR = "data/interim"
    MAX_FILES = 5  # Set to None for full dataset

    # Create directories
    os.makedirs(INTERIM_DIR, exist_ok=True)

    logging.info("Starting MPD Dataset Enrichment Pipeline")
    logging.info("=" * 60)

    # Step 1: Extract unique tracks
    logging.info("Step 1: Extracting unique tracks from MPD...")
    unique_tracks, track_frequency = extract_unique_tracks_from_mpd(
        DATA_DIR, max_files=MAX_FILES
    )

    # Step 2: Save track data
    tracks_file = f"{INTERIM_DIR}/unique_tracks.json"
    save_track_data(unique_tracks, track_frequency, tracks_file)

    # Step 3: Collect audio features (if credentials available)
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")

    # Debug: Check if credentials are loaded
    logging.debug(f"Client ID loaded: {'Yes' if client_id else 'No'}")
    logging.debug(f"Client Secret loaded: {'Yes' if client_secret else 'No'}")

    if client_id and client_secret:
        logging.info("Step 2: Collecting audio features from Spotify...")

        try:
            collector = SpotifyAudioFeatureCollector(client_id, client_secret)

            track_uris = list(unique_tracks.keys())
            audio_features = collector.collect_all_audio_features(
                track_uris=track_uris,
                output_file=f"{INTERIM_DIR}/audio_features.json",
                batch_size=100,
                delay=0.1,
            )

            logging.debug(f"Collected audio features for {len(audio_features)} tracks")
            logging.success("Audio feature collection complete!")

        except Exception as e:
            logging.error(f"Audio feature collection failed: {e}")

    else:
        logging.warning("Spotify credentials not found.")
        logging.info("Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env file")
        logging.info("Audio feature collection skipped.")

    logging.success("Dataset enrichment pipeline complete!")


if __name__ == "__main__":
    main()
