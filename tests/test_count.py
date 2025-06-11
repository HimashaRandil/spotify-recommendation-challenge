#!/usr/bin/env python3
"""
Count playlists in the Spotify Million Playlist Dataset
Handles both single files and directory of slice files
"""

import json
import os
import sys
from pathlib import Path


def count_playlists_in_file(file_path):
    """Count playlists in a single JSON file"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if "playlists" in data:
            playlist_count = len(data["playlists"])
            print(f"📁 {file_path.name}: {playlist_count:,} playlists")
            return playlist_count
        else:
            print(f"❌ {file_path.name}: No 'playlists' key found")
            return 0

    except json.JSONDecodeError as e:
        print(f"❌ {file_path.name}: JSON decode error - {e}")
        return 0
    except FileNotFoundError:
        print(f"❌ {file_path}: File not found")
        return 0
    except Exception as e:
        print(f"❌ {file_path.name}: Error - {e}")
        return 0


def count_playlists_in_directory(directory_path):
    """Count playlists in all JSON files in a directory"""
    directory = Path(directory_path)

    if not directory.exists():
        print(f"❌ Directory {directory_path} does not exist")
        return 0

    # Find all JSON files that look like MPD slices
    json_files = []

    # Look for standard MPD slice files
    mpd_slice_files = list(directory.glob("mpd.slice.*.json"))
    if mpd_slice_files:
        json_files.extend(sorted(mpd_slice_files))
        print(f"📂 Found {len(mpd_slice_files)} MPD slice files")

    # Look for other JSON files if no slice files found
    if not json_files:
        all_json_files = list(directory.glob("*.json"))
        if all_json_files:
            json_files.extend(sorted(all_json_files))
            print(f"📂 Found {len(all_json_files)} JSON files")

    if not json_files:
        print(f"❌ No JSON files found in {directory_path}")
        return 0

    total_playlists = 0
    files_processed = 0

    print("\n🔍 Processing files...")
    print("-" * 50)

    for json_file in json_files:
        playlist_count = count_playlists_in_file(json_file)
        total_playlists += playlist_count
        files_processed += 1

        # Show progress for large numbers of files
        if files_processed % 10 == 0:
            print(f"   Processed {files_processed}/{len(json_files)} files...")

    return total_playlists, files_processed, len(json_files)


def analyze_dataset_structure(directory_path):
    """Analyze the structure of the dataset"""
    directory = Path(directory_path)

    print("🔍 Dataset Structure Analysis")
    print("=" * 50)
    print(f"📂 Directory: {directory_path}")

    # List all files
    all_files = list(directory.iterdir())
    json_files = [f for f in all_files if f.suffix == ".json"]

    print(f"📊 Total files: {len(all_files)}")
    print(f"📄 JSON files: {len(json_files)}")

    if json_files:
        print("\n📝 JSON Files Found:")
        for i, json_file in enumerate(sorted(json_files)[:10]):  # Show first 10
            file_size = json_file.stat().st_size / (1024 * 1024)  # MB
            print(f"   {json_file.name} ({file_size:.1f} MB)")

        if len(json_files) > 10:
            print(f"   ... and {len(json_files) - 10} more files")

    print("\n" + "=" * 50)


def main():
    """Main function to count playlists"""
    print("🎵 Spotify Dataset Playlist Counter")
    print("=" * 50)

    # Default to current directory's data folder
    default_paths = ["data/raw", "data", ".", "../data/raw", "../data"]

    # Check if path provided as argument
    if len(sys.argv) > 1:
        data_path = sys.argv[1]
    else:
        # Try to find data directory
        data_path = None
        for path in default_paths:
            if os.path.exists(path):
                json_files = list(Path(path).glob("*.json"))
                if json_files:
                    data_path = path
                    print(f"📂 Found data in: {path}")
                    break

        if not data_path:
            print("❌ No data directory found. Please specify path:")
            print("   python count_playlists.py /path/to/data")
            print("\n🔍 Looked in:")
            for path in default_paths:
                print(f"   {path}")
            return

    # Analyze structure first
    analyze_dataset_structure(data_path)

    # Count playlists
    print("\n🔢 Counting Playlists...")
    print("=" * 50)

    path = Path(data_path)

    if path.is_file():
        # Single file
        print(f"📄 Processing single file: {path.name}")
        total_playlists = count_playlists_in_file(path)
        files_processed = 1
        total_files = 1
    else:
        # Directory
        result = count_playlists_in_directory(data_path)
        if isinstance(result, tuple):
            total_playlists, files_processed, total_files = result
        else:
            total_playlists = result
            files_processed = 0
            total_files = 0

    # Summary
    print("\n" + "=" * 50)
    print("📊 SUMMARY")
    print("=" * 50)
    print(f"📁 Files processed: {files_processed}/{total_files}")
    print(f"🎵 Total playlists: {total_playlists:,}")

    # Determine dataset type
    if total_playlists == 1000000:
        print("✅ This appears to be the complete Million Playlist Dataset (MPD)")
    elif total_playlists == 10000:
        print("✅ This appears to be the Challenge Dataset")
    elif total_playlists > 1000000:
        print("🤔 This has more than 1M playlists - might include additional data")
    elif total_playlists < 10000:
        print("🤔 This appears to be a sample or subset of the data")
    else:
        print("🤔 Custom dataset size")

    print("\n✅ Analysis complete!")


if __name__ == "__main__":
    main()
