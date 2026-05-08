#!/usr/bin/env python3
"""
war.gov/UFO — Release 01 (May 8, 2026)
Downloads 133 PDFs/images directly + 28 videos via DVIDS API.

Usage:
    python3 download-ufo-release1.py [output_dir] [--jobs N]

Defaults: output_dir=<project>/data, jobs=5
"""

import argparse
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from curl_cffi import requests as cffi_requests

DVIDS_KEY = "key-68bb60d16b35e"
DVIDS_API = "https://api.dvidshub.net/asset?api_key={key}&id=video:{vid}&thumb_width=720"
IMPERSONATE = "chrome124"

DIRECT_URLS = [
    "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_section_10.pdf",
    "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_section_2.pdf",
    "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_section_3.pdf",
    "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_section_4.pdf",
    "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_section_5.pdf",
    "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_section_6.pdf",
    "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_section_7.pdf",
    "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_section_9.pdf",
    "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_serial_130.pdf",
    "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_serial_153.pdf",
    "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_serial_164.pdf",
    "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_serial_220.pdf",
    "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_serial_403.pdf",
    "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_serial_438.pdf",
    "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_serial_449.pdf",
    "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_sub_a.pdf",
    "https://www.war.gov/medialink/ufo/release_1/18_100754_ general 1946-7_vol_2.pdf",
    "https://www.war.gov/medialink/ufo/release_1/18_6369445_general_1948_vol_1.pdf",
    "https://www.war.gov/medialink/ufo/release_1/255_413270_ufo's_and_defense_what_should_we_prepare_for.pdf",
    "https://www.war.gov/medialink/ufo/release_1/255_t_763_r1b_transcripts.pdf",
    "https://www.war.gov/medialink/ufo/release_1/331_120752_numeric_files_1944–1945_37153_german_armament_equipment_documents.pdf",
    "https://www.war.gov/medialink/ufo/release_1/341_110448_records_relating_to_the_collection_and_dissemination_of_intelligence_1948-1955-ts_cont_no.2_2-5300-2-5399.pdf",
    "https://www.war.gov/medialink/ufo/release_1/341_110677_numerical_file_5-2500.pdf",
    "https://www.war.gov/medialink/ufo/release_1/342_hs1-416511228_box186_319.1-flying-discs-1949.pdf",
    "https://www.war.gov/medialink/ufo/release_1/38_143685_box7_incident_summaries_101-172.pdf",
    "https://www.war.gov/medialink/ufo/release_1/38_143685_box7_incident_summaries_173-233.pdf",
    "https://www.war.gov/medialink/ufo/release_1/38_143685_box7_incident_summaries_1-100.pdf",
    "https://www.war.gov/medialink/ufo/release_1/59_214434_sp_16_[7.18.1963].pdf",
    "https://www.war.gov/medialink/ufo/release_1/59_214434_sp_16_7.18.1963.pdf",
    "https://www.war.gov/medialink/ufo/release_1/65_hs1-101634279_100-de-18221_serial_844.pdf",
    "https://www.war.gov/medialink/ufo/release_1/65_hs1-101634279_100-de-26505.pdf",
    "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_section_1.pdf",
    "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_section_8.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d10-mission-report-middle-east-may-2022.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d12-mission-report-iraq-may-2022.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d14-mission-report-iraq-may-2022.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d16-mission-report-syria-july-2022.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d18-mission-report-iraq-december-2022.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d19-mission-report-syria-february-21-2023.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d20-mission-report-southern-united-states-2023.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d23-mission-report-united-arab-emirates-october-2023.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d25-mission-report-greece-january-2024.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d27-mission-report-united-arab-emirates-october-2023.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d28-mission-report-east-china-sea-2024.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d3-mission-report-arabian-gulf-2020.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d32-mission-report,-syria-october-2024.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d33-mission-report-greece-october-2023.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d35-mission-report-greece-october-2023.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d38-range-fouler-debrief-middle-east-may-2020.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d4-mission-report-arabian-gulf-2020.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d42-range-fouler-debrief-japan-2023.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d44-range-fouler-arabian-sea-october-2020.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d48-report-september-1996.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d49-launch-summary-february-2000.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d5-mission-report-arabian-gulf-2020.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d50-email-correspondence-indopacom-april-2025.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d51-email-correspondence-pacific-time-zone-march-2023.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d52-email-correspondance-na-august-2024.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d54-mission-report-mediterranean-sea-na.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d55-mission-report-syria-november-2016.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d56-range-fouler-debrief-arabian-sea-august-2020.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d57-mission-report-gulf-of-aden-september-2020.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d58-range-fouler-debrief-na-october-2020.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d6-mission-report-arabian-gulf-2020.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d60-mission-report-persian-gulf-august-2020.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d61-mission-report-persian-gulf-august-2020.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d62-mission-report-strait-of-hormuz-september-2020.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d63-mission-report-strait-of-hormuz-october-2020.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d64-mission-report-iran-november-2020.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d65-mission-report-persian-gulf-july-2020.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d7-mission-report-arabian-gulf-2020.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d74-mission-report-syria-november-2023.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d75-mission-report-gulf-of-aden-july-2024.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-d8-mission-report-djibouti-2025.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dow-uap-pr20.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-a1.png",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-a2.png",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-a3.png",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-a4.png",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-a5.png",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-a6.png",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-a7.png",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-a8.png",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b1.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b10.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b11.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b12.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b13.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b14.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b15.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b16.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b17.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b18.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b19.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b2.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b20.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b21.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b22.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b23.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b24.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b3.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b4.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b5.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b6.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b7.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b8.pdf",
    "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b9.pdf",
    "https://www.war.gov/medialink/ufo/release_1/nasa-uap-d1-apollo-12-transcript-1969.pdf",
    "https://www.war.gov/medialink/ufo/release_1/nasa-uap-d2-apollo-17-transcript-1972.pdf",
    "https://www.war.gov/medialink/ufo/release_1/nasa-uap-d4-apollo-11-technical-crew-debriefing-1969.pdf",
    "https://www.war.gov/medialink/ufo/release_1/nasa-uap-d5-apollo-17-crew-debriefing-for-science-1973.pdf",
    "https://www.war.gov/medialink/ufo/release_1/nasa-uap-d6-apollo-17-technical-crew-debriefing-1973.pdf",
    "https://www.war.gov/medialink/ufo/release_1/nasa-uap-d7-skylab-technical-crew-debriefing-1973.pdf",
    "https://www.war.gov/medialink/ufo/release_1/nasa-uap-vm1-apollo-12-1969.jpg",
    "https://www.war.gov/medialink/ufo/release_1/nasa-uap-vm2-apollo-12-1969.jpg",
    "https://www.war.gov/medialink/ufo/release_1/nasa-uap-vm3-apollo-12-1969.jpg",
    "https://www.war.gov/medialink/ufo/release_1/nasa-uap-vm4-apollo-12-1969.jpg",
    "https://www.war.gov/medialink/ufo/release_1/nasa-uap-vm5-apollo-12-1969.jpg",
    "https://www.war.gov/medialink/ufo/release_1/nasa-uap-vm6-apollo-17-1972.jpg",
    "https://www.war.gov/medialink/ufo/release_1/dos-uap-d1-cable-1-papua-new-guinea-january-1985.pdf",
    "https://www.war.gov/medialink/ufo/release_1/dos-uap-d2-cable-2-kazakhstan-january-1994.pdf",
    "https://www.war.gov/medialink/ufo/release_1/059uap00011.pdf",
    "https://www.war.gov/medialink/ufo/release_1/059uap00012.pdf",
    "https://www.war.gov/medialink/ufo/release_1/059uap00013.pdf",
    "https://www.war.gov/medialink/ufo/release_1/usper-statement-redacted.pdf",
    "https://www.war.gov/medialink/ufo/release_1/2024-04-30-composite-sketch.pdf",
    "https://www.war.gov/medialink/ufo/release_1/serial 5 redacted_redacted.pdf",
    "https://www.war.gov/medialink/ufo/release_1/serial-3_redacted.pdf",
    "https://www.war.gov/medialink/ufo/release_1/serial-4-redacted_redacted.pdf",
    "https://www.war.gov/medialink/ufo/release_1/western_us_event_slides_5.08.2026.pdf",
]

VIDEO_IDS = [
    "1006119",  # NASA-UAP-D3A, Gemini 7 Audio Excerpt, 1965
    "1006056",  # DOW-UAP-PR19, Middle East, May 2022
    "1006059",  # DOW-UAP-PR21, Iraq, May 2022
    "1006060",  # DOW-UAP-PR22, Syria, July 2022
    "1006062",  # DOW-UAP-PR23, Iraq, December 2022
    "1006063",  # DOW-UAP-PR26, UAE, October 2023
    "1006067",  # DOW-UAP-PR27, UAE, October 2023
    "1006073",  # DOW-UAP-PR28, Greece, January 2024
    "1006074",  # DOW-UAP-PR29, UAE, June 2024
    "1006076",  # DOW-UAP-PR31, Syria, October 2024
    "1006078",  # DOW-UAP-PR32, Syria, October 2024
    "1006079",
    "1006080",
    "1006082",
    "1006083",
    "1006087",
    "1006088",
    "1006089",
    "1006093",
    "1006094",
    "1006097",
    "1006159",
    "1006104",
    "1006105",
    "1006106",
    "1006107",
    "1006110",
    "1006111",
]

HEADERS = {"Referer": "https://www.war.gov/UFO/"}


def fetch_url(url: str, dest: Path, label: str) -> tuple[str, bool, str]:
    if dest.exists():
        return label, True, "skipped"
    try:
        r = cffi_requests.get(url, headers=HEADERS, impersonate=IMPERSONATE, timeout=600, stream=True)
        r.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                f.write(chunk)
        return label, True, "ok"
    except Exception as e:
        dest.unlink(missing_ok=True)
        return label, False, str(e)


def resolve_video(vid_id: str) -> tuple[str | None, str | None]:
    """Return (mp4_url, sanitized_title) or (None, None) on failure."""
    api_url = DVIDS_API.format(key=DVIDS_KEY, vid=vid_id)
    try:
        r = cffi_requests.get(
            api_url, impersonate=IMPERSONATE, timeout=15,
            headers={
                "Referer": "https://www.war.gov/UFO/",
                "Origin": "https://www.war.gov",
            },
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"    API error for {vid_id}: {e}")
        return None, None

    record = data.get("results") or data.get("data") or data
    files = record.get("files", [])
    mp4s = [f for f in files if f.get("type") == "video/mp4"]
    if not mp4s:
        return None, None

    best = max(mp4s, key=lambda f: f.get("height", 0))
    title = re.sub(r"[^\w\s-]", "", record.get("title", "")).strip()
    title = re.sub(r"\s+", "_", title)[:80]
    return best["src"], title or None


def download_direct(urls: list[str], out: Path, jobs: int) -> dict:
    counts = {"ok": 0, "skipped": 0, "error": 0}
    image_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp"}

    def make_dest(url):
        name = Path(url.split("?")[0]).name
        ext = Path(name).suffix.lower()
        subdir = "images" if ext in image_exts else "pdfs"
        return out / subdir / name

    tasks = {url: make_dest(url) for url in urls}

    print(f"=== Downloading {len(urls)} PDFs/images ({jobs} parallel) ===")
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {
            pool.submit(fetch_url, url, dest, Path(url).name): url
            for url, dest in tasks.items()
        }
        for i, future in enumerate(as_completed(futures), 1):
            label, ok, status = future.result()
            if status == "skipped":
                counts["skipped"] += 1
                print(f"  [{i:3}/{len(urls)}] skip  {label}")
            elif ok:
                counts["ok"] += 1
                print(f"  [{i:3}/{len(urls)}] ok    {label}")
            else:
                counts["error"] += 1
                print(f"  [{i:3}/{len(urls)}] ERROR {label}: {status}")

    return counts


def download_videos(video_ids: list[str], out: Path, jobs: int) -> dict:
    counts = {"ok": 0, "skipped": 0, "error": 0}
    print(f"\n=== Resolving + downloading {len(video_ids)} videos ===")

    def handle(vid_id):
        mp4_url, title = resolve_video(vid_id)
        if not mp4_url:
            return vid_id, False, "no MP4 found"
        filename = f"{vid_id}_{title}.mp4" if title else f"{vid_id}.mp4"
        dest = out / "videos" / filename
        return fetch_url(mp4_url, dest, filename)

    with ThreadPoolExecutor(max_workers=jobs) as pool:
        futures = {pool.submit(handle, vid): vid for vid in video_ids}
        for i, future in enumerate(as_completed(futures), 1):
            label, ok, status = future.result()
            if status == "skipped":
                counts["skipped"] += 1
                print(f"  [{i:2}/{len(video_ids)}] skip  {label}")
            elif ok:
                counts["ok"] += 1
                print(f"  [{i:2}/{len(video_ids)}] ok    {label}")
            else:
                counts["error"] += 1
                print(f"  [{i:2}/{len(video_ids)}] ERROR {label}: {status}")

    return counts


def human_size(path: Path) -> str:
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    for unit in ("B", "KB", "MB", "GB"):
        if total < 1024:
            return f"{total:.1f} {unit}"
        total /= 1024
    return f"{total:.1f} TB"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "output_dir",
        nargs="?",
        default=str(Path(__file__).parent / "data"),
    )
    parser.add_argument("--jobs", type=int, default=5, help="parallel downloads")
    args = parser.parse_args()

    out = Path(args.output_dir)
    for subdir in ("pdfs", "images", "videos"):
        (out / subdir).mkdir(parents=True, exist_ok=True)

    print(f"Output: {out}")
    print(f"Parallel jobs: {args.jobs}\n")

    dc = download_direct(DIRECT_URLS, out, args.jobs)
    vc = download_videos(VIDEO_IDS, out, args.jobs)

    print("\n=== Summary ===")
    print(f"  PDFs/images — ok: {dc['ok']}, skipped: {dc['skipped']}, errors: {dc['error']}")
    print(f"  Videos      — ok: {vc['ok']}, skipped: {vc['skipped']}, errors: {vc['error']}")
    print(f"  Total size: {human_size(out)}")
    print(f"  Location:   {out}")


if __name__ == "__main__":
    main()
