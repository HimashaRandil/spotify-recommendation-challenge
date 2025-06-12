#!/usr/bin/env python3
"""
MPD data extraction utilities
"""

import json
import os
from pathlib import Path
from collections import Counter
from typing import Dict, Optional, Tuple
from tqdm import tqdm

from src.utils.logger.logging import logger as logging


def extract_unique_tracks_from_mpd(
    data_dir: str, max_files: Optional[int] = None
) -> Tuple[Dict[str, Dict], Counter]:
    """
    Extract unique track URIs and metadata from MPD dataset

    Args:
        data_dir: Path to MPD data directory
        max_files: Limit files for testing (None = all files)

    Returns:
        Tuple of (unique_tracks_dict, track_frequency_counter)
    """

    logging.info("Extracting Track URIs from MPD Dataset")

    data_path = Path(data_dir)
    slice_files = sorted(list(data_path.glob("mpd.slice.*.json")))

    if max_files:
        slice_files = slice_files[:max_files]
        logging.info(f"Processing first {len(slice_files)} files for testing...")
    else:
        logging.info(f"Processing all {len(slice_files)} files...")

    unique_tracks = {}
    track_frequency = Counter()
    total_tracks_processed = 0

    for slice_file in tqdm(slice_files, desc="Processing files"):
        try:
            with open(slice_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for playlist in data["playlists"]:
                for track in playlist["tracks"]:
                    track_uri = track["track_uri"]
                    track_frequency[track_uri] += 1
                    total_tracks_processed += 1

                    if track_uri not in unique_tracks:
                        unique_tracks[track_uri] = {
                            "track_uri": track_uri,
                            "track_name": track["track_name"],
                            "artist_name": track["artist_name"],
                            "artist_uri": track["artist_uri"],
                            "album_name": track["album_name"],
                            "album_uri": track["album_uri"],
                            "duration_ms": track["duration_ms"],
                        }

        except Exception as e:
            logging.error(f"Error processing {slice_file}: {e}")
            continue

    logging.info(f"   Total track instances: {total_tracks_processed:,}")
    logging.info(f"   Unique tracks: {len(unique_tracks):,}")
    logging.info(
        f"   Average frequency: {total_tracks_processed / len(unique_tracks):.1f}"
    )

    return unique_tracks, track_frequency


def save_track_data(
    unique_tracks: Dict[str, Dict], track_frequency: Counter, output_file: str
) -> None:
    """Save extracted track data to JSON file"""

    # Create output directory if needed
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    tracks_data = {
        "tracks": list(unique_tracks.values()),
        "frequencies": dict(track_frequency),
        "summary": {
            "unique_tracks": len(unique_tracks),
            "total_instances": sum(track_frequency.values()),
        },
    }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(tracks_data, f, indent=2, ensure_ascii=False)

    logging.success(f"✅ Saved {len(unique_tracks):,} unique tracks to: {output_file}")
