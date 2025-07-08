#!/usr/bin/env python3
"""
Extract unique albums from MPD dataset
"""

import json
import os
from pathlib import Path
from collections import Counter
from typing import Dict, Optional, Tuple
from tqdm import tqdm
import datetime

from src.utils.logger.logging import logger as logging


def load_checkpoint(
    checkpoint_file: str,
) -> Tuple[Dict[str, Dict], Counter, set, int, int]:
    """Load checkpoint data if exists"""

    if not os.path.exists(checkpoint_file):
        logging.info("📍 No checkpoint found, starting fresh")
        return {}, Counter(), set(), 0, 0

    try:
        with open(checkpoint_file, "r", encoding="utf-8") as f:
            checkpoint_data = json.load(f)

        unique_albums = {
            uri: data for uri, data in checkpoint_data["unique_albums"].items()
        }
        album_frequency = Counter(checkpoint_data["album_frequency"])
        processed_files = set(checkpoint_data["processed_files"])
        total_tracks = checkpoint_data["total_tracks_processed"]
        total_playlists = checkpoint_data["playlists_processed"]

        logging.info(
            f"📍 Checkpoint loaded: {len(unique_albums):,} albums, {len(processed_files)} files processed"
        )
        return (
            unique_albums,
            album_frequency,
            processed_files,
            total_tracks,
            total_playlists,
        )

    except Exception as e:
        logging.error(f"❌ Error loading checkpoint: {e}")
        logging.info("📍 Starting fresh due to checkpoint error")
        return {}, Counter(), set(), 0, 0


def save_checkpoint(
    unique_albums: Dict[str, Dict],
    album_frequency: Counter,
    processed_files: set,
    total_tracks: int,
    total_playlists: int,
    checkpoint_file: str,
):
    """Save checkpoint data"""

    try:
        checkpoint_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "unique_albums": unique_albums,
            "album_frequency": dict(album_frequency),
            "processed_files": list(processed_files),
            "total_tracks_processed": total_tracks,
            "playlists_processed": total_playlists,
            "summary": {
                "unique_albums_count": len(unique_albums),
                "files_processed": len(processed_files),
                "total_tracks": total_tracks,
            },
        }

        os.makedirs(os.path.dirname(checkpoint_file), exist_ok=True)
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(checkpoint_data, f, indent=2, ensure_ascii=False)

    except Exception as e:
        logging.error(f"❌ Error saving checkpoint: {e}")


def extract_unique_albums_from_mpd(
    data_dir: str,
    max_files: Optional[int] = None,
    testing_mode: bool = False,
    checkpoint_file: str = "data/interim/album_extraction_checkpoint.json",
) -> Tuple[Dict[str, Dict], Counter]:
    """
    Extract unique album URIs and metadata from MPD dataset with checkpoint support

    Args:
        data_dir: Path to MPD data directory (raw folder)
        max_files: Limit files for testing (None = all files)
        testing_mode: If True, process only first 2 playlists total
        checkpoint_file: Path to checkpoint file for resume functionality

    Returns:
        Tuple of (unique_albums_dict, album_frequency_counter)
    """

    logging.info("💿 Extracting Unique Albums from MPD Dataset")

    if testing_mode:
        logging.info("🧪 TESTING MODE: Processing only first 2 playlists")

    data_path = Path(data_dir)
    slice_files = sorted(list(data_path.glob("mpd.slice.*.json")))

    if not slice_files:
        logging.error(f"❌ No MPD slice files found in {data_dir}")
        raise FileNotFoundError(f"No MPD slice files found in {data_dir}")

    # Load checkpoint
    (
        unique_albums,
        album_frequency,
        processed_files,
        total_tracks_processed,
        playlists_processed,
    ) = load_checkpoint(checkpoint_file)

    if max_files:
        slice_files = slice_files[:max_files]
        logging.info(f"📊 Processing first {len(slice_files)} files for testing...")
    else:
        logging.info(f"📊 Processing all {len(slice_files)} files...")

    # Filter out already processed files
    remaining_files = [f for f in slice_files if str(f) not in processed_files]

    if not remaining_files:
        logging.info("✅ All files already processed!")
        return unique_albums, album_frequency

    logging.info(f"📁 Files remaining: {len(remaining_files)}/{len(slice_files)}")

    total_playlists_to_process = 2 if testing_mode else float("inf")
    playlists_processed_in_session = 0

    for slice_file in tqdm(remaining_files, desc="Processing MPD files"):
        if testing_mode and playlists_processed >= total_playlists_to_process:
            logging.info(
                f"🧪 Testing limit reached: {total_playlists_to_process} playlists"
            )
            break

        try:
            with open(slice_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            file_playlists_processed = 0
            for playlist in data["playlists"]:
                if testing_mode and playlists_processed >= total_playlists_to_process:
                    break

                playlists_processed += 1
                file_playlists_processed += 1
                playlists_processed_in_session += 1

                for track in playlist["tracks"]:
                    album_uri = track["album_uri"]
                    album_name = track["album_name"]
                    artist_name = track["artist_name"]
                    artist_uri = track["artist_uri"]

                    # Count frequency of album appearances
                    album_frequency[album_uri] += 1
                    total_tracks_processed += 1

                    # Store unique album info (simplified - only name and URI)
                    if album_uri not in unique_albums:
                        unique_albums[album_uri] = {
                            "album_uri": album_uri,
                            "album_name": album_name,
                            "artist_name": artist_name,  # Primary artist for the album
                            "artist_uri": artist_uri,  # Primary artist URI
                            "spotify_id": extract_spotify_id_from_uri(album_uri),
                        }

            # Mark file as processed
            processed_files.add(str(slice_file))

            # Save checkpoint every 5 files or in testing mode
            if len(processed_files) % 5 == 0 or testing_mode:
                save_checkpoint(
                    unique_albums,
                    album_frequency,
                    processed_files,
                    total_tracks_processed,
                    playlists_processed,
                    checkpoint_file,
                )
                logging.info(
                    f"💾 Checkpoint saved: {len(unique_albums):,} albums, {len(processed_files)} files"
                )

            logging.info(
                f"📄 Processed {slice_file.name}: {file_playlists_processed} playlists"
            )

        except Exception as e:
            logging.error(f"❌ Error processing {slice_file}: {e}")
            continue

    # Final checkpoint save
    save_checkpoint(
        unique_albums,
        album_frequency,
        processed_files,
        total_tracks_processed,
        playlists_processed,
        checkpoint_file,
    )

    # Calculate final statistics
    logging.info("📈 Extraction Summary:")
    logging.info(f"   Files processed this session: {len(remaining_files)}")
    logging.info(f"   Total files processed: {len(processed_files)}")
    logging.info(
        f"   Playlists processed this session: {playlists_processed_in_session:,}"
    )
    logging.info(f"   Total playlists processed: {playlists_processed:,}")
    logging.info(f"   Total track instances: {total_tracks_processed:,}")
    logging.info(f"   Unique albums found: {len(unique_albums):,}")

    if len(unique_albums) > 0:
        logging.info(
            f"   Average tracks per album: {total_tracks_processed / len(unique_albums):.1f}"
        )

        # Top albums by frequency
        top_albums = album_frequency.most_common(10)
        logging.info("💿 Top 10 Most Frequent Albums:")
        for i, (album_uri, count) in enumerate(top_albums, 1):
            album_name = unique_albums[album_uri]["album_name"]
            artist_name = unique_albums[album_uri]["artist_name"]
            logging.info(f"   {i:2d}. {album_name} by {artist_name} ({count:,} tracks)")

    return unique_albums, album_frequency


def extract_spotify_id_from_uri(album_uri: str) -> str:
    """Extract Spotify ID from album URI"""
    if album_uri.startswith("spotify:album:"):
        return album_uri.split(":")[-1]
    else:
        return album_uri  # Assume it's already an ID


def save_album_data(
    unique_albums: Dict[str, Dict], album_frequency: Counter, output_file: str
) -> None:
    """Save extracted album data to JSON file in interim folder"""

    # Create output directory if needed
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    # Prepare simplified data structure
    albums_data = {
        "metadata": {
            "extraction_date": datetime.datetime.now().isoformat(),
            "total_unique_albums": len(unique_albums),
            "total_album_instances": sum(album_frequency.values()),
            "description": "Unique albums extracted from Spotify Million Playlist Dataset",
        },
        "albums": list(unique_albums.values()),
        "frequency_stats": {
            "top_10_most_frequent": [
                {
                    "album_uri": uri,
                    "album_name": unique_albums[uri]["album_name"],
                    "artist_name": unique_albums[uri]["artist_name"],
                    "frequency": count,
                }
                for uri, count in album_frequency.most_common(10)
            ],
        },
    }

    # Save to JSON
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(albums_data, f, indent=2, ensure_ascii=False)

    logging.success(f"✅ Saved {len(unique_albums):,} unique albums to: {output_file}")


def main():
    """Main execution function"""

    # Configuration
    RAW_DATA_DIR = "data/raw"
    INTERIM_OUTPUT_FILE = "data/interim/unique_albums.json"
    CHECKPOINT_FILE = "data/interim/album_extraction_checkpoint.json"

    # ===== CONFIGURATION FLAGS =====
    TESTING_MODE = False  # Set to True for testing with only 2 playlists
    MAX_FILES_FOR_TESTING = None  # Set to small number to limit files (e.g., 2)

    # Remove existing checkpoint if starting fresh
    FRESH_START = False  # Set to True to ignore existing checkpoint

    if FRESH_START and os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        logging.info("🗑️  Removed existing checkpoint for fresh start")

    try:
        # Extract unique albums with checkpoint support
        unique_albums, album_frequency = extract_unique_albums_from_mpd(
            data_dir=RAW_DATA_DIR,
            max_files=MAX_FILES_FOR_TESTING,
            testing_mode=TESTING_MODE,
            checkpoint_file=CHECKPOINT_FILE,
        )

        # Save to interim folder
        save_album_data(unique_albums, album_frequency, INTERIM_OUTPUT_FILE)

        logging.success("🎉 Album extraction completed successfully!")

        if TESTING_MODE:
            logging.info(
                "🧪 Testing mode completed. Set TESTING_MODE=False for full extraction."
            )

        # Clean up checkpoint file after successful completion (optional)
        if os.path.exists(CHECKPOINT_FILE) and not TESTING_MODE:
            # Rename checkpoint to backup instead of deleting
            backup_file = CHECKPOINT_FILE.replace(".json", "_completed.json")
            os.rename(CHECKPOINT_FILE, backup_file)
            logging.info(f"💾 Checkpoint backed up to: {backup_file}")

    except Exception as e:
        logging.error(f"❌ Album extraction failed: {e}")
        logging.info(f"💾 Progress saved in checkpoint: {CHECKPOINT_FILE}")
        logging.info("📝 You can resume by running the script again")
        raise


if __name__ == "__main__":
    main()
