#!/usr/bin/env python3
"""
Extract unique artists from MPD dataset with checkpoint/resume functionality
"""

import json
import os
from pathlib import Path
from collections import Counter
from typing import Dict, Optional, Tuple
from tqdm import tqdm

from src.utils.logger.logging import logger as logging


def extract_unique_artists_from_mpd(
    data_dir: str, max_files: Optional[int] = None
) -> Tuple[Dict[str, Dict], Counter]:
    """
    Extract unique artist URIs and metadata from MPD dataset

    Args:
        data_dir: Path to MPD data directory (raw folder)
        max_files: Limit files for testing (None = all files)

    Returns:
        Tuple of (unique_artists_dict, artist_frequency_counter)
    """

    logging.info("🎤 Extracting Unique Artists from MPD Dataset")

    data_path = Path(data_dir)
    slice_files = sorted(list(data_path.glob("mpd.slice.*.json")))

    if not slice_files:
        raise FileNotFoundError(f"No MPD slice files found in {data_dir}")

    if max_files:
        slice_files = slice_files[:max_files]
        logging.info(f"📊 Processing first {len(slice_files)} files for testing...")
    else:
        logging.info(f"📊 Processing all {len(slice_files)} files...")

    unique_artists = {}
    artist_frequency = Counter()
    total_tracks_processed = 0
    playlists_processed = 0

    for slice_file in tqdm(slice_files, desc="Processing MPD files"):
        try:
            with open(slice_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for playlist in data["playlists"]:
                playlists_processed += 1

                for track in playlist["tracks"]:
                    artist_uri = track["artist_uri"]
                    artist_name = track["artist_name"]

                    # Count frequency of artist appearances
                    artist_frequency[artist_uri] += 1
                    total_tracks_processed += 1

                    # Store unique artist info
                    if artist_uri not in unique_artists:
                        unique_artists[artist_uri] = {
                            "artist_uri": artist_uri,
                            "artist_name": artist_name,
                            "first_seen_in_playlist": playlist.get("pid", "unknown"),
                            "track_count": 0,  # Will be updated later
                        }

                    # Update track count for this artist
                    unique_artists[artist_uri]["track_count"] += 1

        except Exception as e:
            logging.error(f"❌ Error processing {slice_file}: {e}")
            continue

    # Calculate final statistics
    logging.info("📈 Extraction Summary:")
    logging.info(f"   Files processed: {len(slice_files)}")
    logging.info(f"   Playlists processed: {playlists_processed:,}")
    logging.info(f"   Total track instances: {total_tracks_processed:,}")
    logging.info(f"   Unique artists found: {len(unique_artists):,}")
    logging.info(
        f"   Average tracks per artist: {total_tracks_processed / len(unique_artists):.1f}"
    )

    # Top artists by frequency
    top_artists = artist_frequency.most_common(10)
    logging.info("🎵 Top 10 Most Frequent Artists:")
    for i, (artist_uri, count) in enumerate(top_artists, 1):
        artist_name = unique_artists[artist_uri]["artist_name"]
        logging.info(f"   {i:2d}. {artist_name} ({count:,} tracks)")

    return unique_artists, artist_frequency


def save_artist_data(
    unique_artists: Dict[str, Dict], artist_frequency: Counter, output_file: str
) -> None:
    """Save extracted artist data to JSON file in interim folder"""

    # Create output directory if needed
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Prepare data structure
    artists_data = {
        "metadata": {
            "extraction_date": None,  # Could add timestamp here
            "total_unique_artists": len(unique_artists),
            "total_artist_instances": sum(artist_frequency.values()),
            "description": "Unique artists extracted from Spotify Million Playlist Dataset",
        },
        "artists": list(unique_artists.values()),
        "frequency_stats": {
            "frequencies": dict(artist_frequency),
            "top_10_most_frequent": [
                {
                    "artist_uri": uri,
                    "artist_name": unique_artists[uri]["artist_name"],
                    "frequency": count,
                }
                for uri, count in artist_frequency.most_common(10)
            ],
        },
    }

    # Save to JSON
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(artists_data, f, indent=2, ensure_ascii=False)

    logging.success(
        f"✅ Saved {len(unique_artists):,} unique artists to: {output_file}"
    )


def main():
    """Main execution function"""

    # Configuration
    RAW_DATA_DIR = "data/raw"
    INTERIM_OUTPUT_FILE = "data/interim/unique_artists.json"

    # For testing, set max_files to a small number (e.g., 2)
    # For full extraction, set to None
    MAX_FILES_FOR_TESTING = None  # Change to 2 for testing

    try:
        # Extract unique artists
        unique_artists, artist_frequency = extract_unique_artists_from_mpd(
            data_dir=RAW_DATA_DIR, max_files=MAX_FILES_FOR_TESTING
        )

        # Save to interim folder
        save_artist_data(unique_artists, artist_frequency, INTERIM_OUTPUT_FILE)

        logging.success("🎉 Artist extraction completed successfully!")

    except Exception as e:
        logging.error(f"❌ Artist extraction failed: {e}")
        raise


if __name__ == "__main__":
    main()
