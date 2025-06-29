import json
import os
import time
import threading
from pathlib import Path
from collections import Counter
from typing import Dict, Optional, Tuple, List
from tqdm import tqdm
import musicbrainzngs
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

from src.utils.logger.logging import logger as logging

# Configure MusicBrainz
musicbrainzngs.set_useragent("TrackFeatureFetcher", "1.0", "contact@example.com")

def get_mbid(artist_name: str, track_name: str) -> Optional[str]:
    try:
        result = musicbrainzngs.search_recordings(recording=track_name, artist=artist_name, limit=1)
        recordings = result.get('recording-list', [])
        if recordings:
            return recordings[0]['id']
    except Exception as e:
        logging.warning(f"MBID fetch failed for {artist_name} - {track_name}: {e}")
    return None

def fetch_acousticbrainz_features(mbid: str, track_name: str, artist_name: str) -> Dict:
    try:
        high_url = f"https://acousticbrainz.org/api/v1/{mbid}/high-level?n=0"
        low_url = f"https://acousticbrainz.org/api/v1/{mbid}/low-level?n=0"

        high_response = requests.get(high_url)
        low_response = requests.get(low_url)

        high_data = high_response.json() if high_response.status_code == 200 else {"message": "Not found"}
        low_data = low_response.json() if low_response.status_code == 200 else {"message": "Not found"}

        if high_data.get("message") == "Not found" and low_data.get("message") == "Not found":
            logging.info(f"No features found for: {track_name} by {artist_name} (MBID: {mbid})")

        return {
            "track_name": track_name,
            "artist_name": artist_name,
            "mbid": mbid,
            "features": {
                "high_level": high_data,
                "low_level": low_data
            }
        }
    except Exception as e:
        logging.warning(f"Feature fetch failed for MBID {mbid}: {e}")
        return {
            "track_name": track_name,
            "artist_name": artist_name,
            "mbid": mbid,
            "features": {
                "high_level": {"message": "Not found"},
                "low_level": {"message": "Not found"}
            }
        }

def extract_tracks_with_features(
    data_dir: str, output_file: str, max_files: Optional[int] = None
) -> None:
    logging.info("Extracting Track Features from MPD Dataset")
    data_path = Path(data_dir)
    slice_files = sorted(list(data_path.glob("mpd.slice.*.json")))

    if max_files:
        slice_files = slice_files[:max_files]
        logging.info(f"Processing first {len(slice_files)} files...")
    else:
        logging.info(f"Processing all {len(slice_files)} files...")

    track_records = []
    mbid_cache = {}
    for slice_file in tqdm(slice_files, desc="Processing files"):
        try:
            with open(slice_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            for playlist in data["playlists"]:
                for track in playlist["tracks"]:
                    track_name = track["track_name"]
                    artist_name = track["artist_name"]
                    key = (track_name.lower(), artist_name.lower())

                    if key in mbid_cache:
                        mbid = mbid_cache[key]
                    else:
                        logging.info(f"Looking up MBID for: {track_name} by {artist_name}")
                        mbid = get_mbid(artist_name, track_name)
                        mbid_cache[key] = mbid
                        time.sleep(1)  # respect rate limits

                    if mbid:
                        track_records.append((track_name, artist_name, mbid))
        except Exception as e:
            logging.error(f"Error processing {slice_file}: {e}")
            continue

    # Use ThreadPoolExecutor for multithreaded feature fetching
    results = []
    logging.info(f"Fetching features for {len(track_records)} tracks using multithreading...")
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(fetch_acousticbrainz_features, mbid, track, artist)
                   for (track, artist, mbid) in track_records]
        for future in tqdm(as_completed(futures), total=len(futures), desc="Fetching features"):
            result = future.result()
            if result:
                results.append(result)

    # Save output to JSON
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    logging.success(f"✅ Saved {len(results):,} tracks with features to: {output_file}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract track features from MPD dataset using AcousticBrainz")
    parser.add_argument("--data_dir", type=str, required=True, help="Path to MPD data directory")
    parser.add_argument("--output_file", type=str, required=True, help="Path to save the JSON output")
    parser.add_argument("--max_files", type=int, default=None, help="Optional limit on number of files to process")

    args = parser.parse_args()

    extract_tracks_with_features(
        data_dir=args.data_dir,
        output_file=args.output_file,
        max_files=args.max_files
    )
