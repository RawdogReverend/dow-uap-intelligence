#!/usr/bin/env bash
# war.gov/UFO — Release 01 (May 8, 2026) — 161 files
# 133 direct (PDFs + images) + 28 videos via DVIDS API

set -euo pipefail

OUT="${1:-$HOME/Downloads/UFO-Release-01}"
DVIDS_KEY="key-68bb60d16b35e"
PARALLEL="${2:-5}"   # concurrent curl jobs

mkdir -p "$OUT/pdfs" "$OUT/images" "$OUT/videos"

echo "Saving to: $OUT"
echo "Parallel downloads: $PARALLEL"
echo ""

# ── Direct files (PDFs + images) ──────────────────────────────────────────────
DIRECT_URLS=(
  "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_section_10.pdf"
  "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_section_2.pdf"
  "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_section_3.pdf"
  "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_section_4.pdf"
  "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_section_5.pdf"
  "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_section_6.pdf"
  "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_section_7.pdf"
  "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_section_9.pdf"
  "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_serial_130.pdf"
  "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_serial_153.pdf"
  "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_serial_164.pdf"
  "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_serial_220.pdf"
  "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_serial_403.pdf"
  "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_serial_438.pdf"
  "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_serial_449.pdf"
  "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_sub_a.pdf"
  "https://www.war.gov/medialink/ufo/release_1/18_100754_ general 1946-7_vol_2.pdf"
  "https://www.war.gov/medialink/ufo/release_1/18_6369445_general_1948_vol_1.pdf"
  "https://www.war.gov/medialink/ufo/release_1/255_413270_ufo's_and_defense_what_should_we_prepare_for.pdf"
  "https://www.war.gov/medialink/ufo/release_1/255_t_763_r1b_transcripts.pdf"
  "https://www.war.gov/medialink/ufo/release_1/331_120752_numeric_files_1944–1945_37153_german_armament_equipment_documents.pdf"
  "https://www.war.gov/medialink/ufo/release_1/341_110448_records_relating_to_the_collection_and_dissemination_of_intelligence_1948-1955-ts_cont_no.2_2-5300-2-5399.pdf"
  "https://www.war.gov/medialink/ufo/release_1/341_110677_numerical_file_5-2500.pdf"
  "https://www.war.gov/medialink/ufo/release_1/342_hs1-416511228_box186_319.1-flying-discs-1949.pdf"
  "https://www.war.gov/medialink/ufo/release_1/38_143685_box7_incident_summaries_101-172.pdf"
  "https://www.war.gov/medialink/ufo/release_1/38_143685_box7_incident_summaries_173-233.pdf"
  "https://www.war.gov/medialink/ufo/release_1/38_143685_box7_incident_summaries_1-100.pdf"
  "https://www.war.gov/medialink/ufo/release_1/59_214434_sp_16_[7.18.1963].pdf"
  "https://www.war.gov/medialink/ufo/release_1/59_214434_sp_16_7.18.1963.pdf"
  "https://www.war.gov/medialink/ufo/release_1/65_hs1-101634279_100-de-18221_serial_844.pdf"
  "https://www.war.gov/medialink/ufo/release_1/65_hs1-101634279_100-de-26505.pdf"
  "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_section_1.pdf"
  "https://www.war.gov/medialink/ufo/release_1/65_hs1-834228961_62-hq-83894_section_8.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d10-mission-report-middle-east-may-2022.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d12-mission-report-iraq-may-2022.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d14-mission-report-iraq-may-2022.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d16-mission-report-syria-july-2022.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d18-mission-report-iraq-december-2022.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d19-mission-report-syria-february-21-2023.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d20-mission-report-southern-united-states-2023.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d23-mission-report-united-arab-emirates-october-2023.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d25-mission-report-greece-january-2024.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d27-mission-report-united-arab-emirates-october-2023.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d28-mission-report-east-china-sea-2024.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d3-mission-report-arabian-gulf-2020.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d32-mission-report,-syria-october-2024.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d33-mission-report-greece-october-2023.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d35-mission-report-greece-october-2023.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d38-range-fouler-debrief-middle-east-may-2020.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d4-mission-report-arabian-gulf-2020.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d42-range-fouler-debrief-japan-2023.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d44-range-fouler-arabian-sea-october-2020.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d48-report-september-1996.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d49-launch-summary-february-2000.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d5-mission-report-arabian-gulf-2020.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d50-email-correspondence-indopacom-april-2025.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d51-email-correspondence-pacific-time-zone-march-2023.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d52-email-correspondance-na-august-2024.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d54-mission-report-mediterranean-sea-na.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d55-mission-report-syria-november-2016.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d56-range-fouler-debrief-arabian-sea-august-2020.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d57-mission-report-gulf-of-aden-september-2020.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d58-range-fouler-debrief-na-october-2020.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d6-mission-report-arabian-gulf-2020.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d60-mission-report-persian-gulf-august-2020.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d61-mission-report-persian-gulf-august-2020.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d62-mission-report-strait-of-hormuz-september-2020.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d63-mission-report-strait-of-hormuz-october-2020.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d64-mission-report-iran-november-2020.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d65-mission-report-persian-gulf-july-2020.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d7-mission-report-arabian-gulf-2020.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d74-mission-report-syria-november-2023.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d75-mission-report-gulf-of-aden-july-2024.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-d8-mission-report-djibouti-2025.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dow-uap-pr20.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-a1.png"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-a2.png"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-a3.png"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-a4.png"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-a5.png"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-a6.png"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-a7.png"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-a8.png"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b1.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b10.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b11.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b12.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b13.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b14.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b15.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b16.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b17.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b18.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b19.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b2.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b20.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b21.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b22.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b23.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b24.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b3.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b4.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b5.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b6.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b7.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b8.pdf"
  "https://www.war.gov/medialink/ufo/release_1/fbi-photo-b9.pdf"
  "https://www.war.gov/medialink/ufo/release_1/nasa-uap-d1-apollo-12-transcript-1969.pdf"
  "https://www.war.gov/medialink/ufo/release_1/nasa-uap-d2-apollo-17-transcript-1972.pdf"
  "https://www.war.gov/medialink/ufo/release_1/nasa-uap-d4-apollo-11-technical-crew-debriefing-1969.pdf"
  "https://www.war.gov/medialink/ufo/release_1/nasa-uap-d5-apollo-17-crew-debriefing-for-science-1973.pdf"
  "https://www.war.gov/medialink/ufo/release_1/nasa-uap-d6-apollo-17-technical-crew-debriefing-1973.pdf"
  "https://www.war.gov/medialink/ufo/release_1/nasa-uap-d7-skylab-technical-crew-debriefing-1973.pdf"
  "https://www.war.gov/medialink/ufo/release_1/nasa-uap-vm1-apollo-12-1969.jpg"
  "https://www.war.gov/medialink/ufo/release_1/nasa-uap-vm2-apollo-12-1969.jpg"
  "https://www.war.gov/medialink/ufo/release_1/nasa-uap-vm3-apollo-12-1969.jpg"
  "https://www.war.gov/medialink/ufo/release_1/nasa-uap-vm4-apollo-12-1969.jpg"
  "https://www.war.gov/medialink/ufo/release_1/nasa-uap-vm5-apollo-12-1969.jpg"
  "https://www.war.gov/medialink/ufo/release_1/nasa-uap-vm6-apollo-17-1972.jpg"
  "https://www.war.gov/medialink/ufo/release_1/dos-uap-d1-cable-1-papua-new-guinea-january-1985.pdf"
  "https://www.war.gov/medialink/ufo/release_1/dos-uap-d2-cable-2-kazakhstan-january-1994.pdf"
  "https://www.war.gov/medialink/ufo/release_1/059uap00011.pdf"
  "https://www.war.gov/medialink/ufo/release_1/059uap00012.pdf"
  "https://www.war.gov/medialink/ufo/release_1/059uap00013.pdf"
  "https://www.war.gov/medialink/ufo/release_1/usper-statement-redacted.pdf"
  "https://www.war.gov/medialink/ufo/release_1/2024-04-30-composite-sketch.pdf"
  "https://www.war.gov/medialink/ufo/release_1/serial 5 redacted_redacted.pdf"
  "https://www.war.gov/medialink/ufo/release_1/serial-3_redacted.pdf"
  "https://www.war.gov/medialink/ufo/release_1/serial-4-redacted_redacted.pdf"
  "https://www.war.gov/medialink/ufo/release_1/western_us_event_slides_5.08.2026.pdf"
)

# ── Video IDs (resolved via DVIDS API) ────────────────────────────────────────
VIDEO_IDS=(
  1006119  # NASA-UAP-D3A, Gemini 7 Audio Excerpt, 1965
  1006056  # DOW-UAP-PR19, Middle East, May 2022
  1006059  # DOW-UAP-PR21, Iraq, May 2022
  1006060  # DOW-UAP-PR22, Syria, July 2022
  1006062  # DOW-UAP-PR23, Iraq, December 2022
  1006063  # DOW-UAP-PR26, UAE, October 2023
  1006067  # DOW-UAP-PR27, UAE, October 2023
  1006073  # DOW-UAP-PR28, Greece, January 2024
  1006074  # DOW-UAP-PR29, UAE, June 2024
  1006076  # DOW-UAP-PR31, Syria, October 2024
  1006078  # DOW-UAP-PR32, Syria, October 2024
  1006079  # DOW-UAP-PR33
  1006080  # DOW-UAP-PR34
  1006082  # DOW-UAP-PR36
  1006083  # DOW-UAP-PR37
  1006087  # DOW-UAP-PR41
  1006088  # DOW-UAP-PR42
  1006089  # DOW-UAP-PR43
  1006093  # DOW-UAP-PR47
  1006094  # DOW-UAP-PR48
  1006097  # DOW-UAP-PR51
  1006159  # DOW-UAP (additional)
  1006104  # DOW-UAP
  1006105  # DOW-UAP
  1006106  # DOW-UAP
  1006107  # DOW-UAP
  1006110  # DOW-UAP
  1006111  # DOW-UAP
)

# ── Download direct files ──────────────────────────────────────────────────────
echo "=== Downloading 133 PDFs/images ==="
jobs=0
for url in "${DIRECT_URLS[@]}"; do
  filename=$(basename "$url")
  # Route to subdir by extension
  ext="${filename##*.}"
  case "$ext" in
    pdf) dest="$OUT/pdfs/$filename" ;;
    png|jpg|jpeg) dest="$OUT/images/$filename" ;;
    *) dest="$OUT/$filename" ;;
  esac

  if [[ -f "$dest" ]]; then
    echo "  skip (exists): $filename"
    continue
  fi

  curl -sSL --retry 3 --retry-delay 2 \
    -A "Mozilla/5.0" \
    -o "$dest" \
    "$url" &

  ((jobs++))
  if (( jobs >= PARALLEL )); then
    wait
    jobs=0
  fi
done
wait
echo "  Done."
echo ""

# ── Download videos via DVIDS API ─────────────────────────────────────────────
echo "=== Downloading 28 videos via DVIDS API ==="
for vid_id in "${VIDEO_IDS[@]}"; do
  dest="$OUT/videos/${vid_id}.mp4"
  if [[ -f "$dest" ]]; then
    echo "  skip (exists): ${vid_id}.mp4"
    continue
  fi

  echo -n "  Resolving video $vid_id ... "
  api_url="https://api.dvidshub.net/asset?api_key=${DVIDS_KEY}&id=video:${vid_id}&thumb_width=720"
  response=$(curl -sSL "$api_url")

  # Extract highest-res MP4 src — pick the last src in files[] sorted by height
  mp4_url=$(echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
files = data.get('results', data.get('data', data)).get('files', [])
mp4s = [f for f in files if f.get('type') == 'video/mp4']
if not mp4s:
    sys.exit(1)
best = sorted(mp4s, key=lambda f: f.get('height', 0), reverse=True)[0]
print(best['src'])
" 2>/dev/null) || { echo "SKIP (no MP4 found)"; continue; }

  # Use title from API if available for a nicer filename
  title=$(echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
r = data.get('results', data.get('data', data))
t = r.get('title', '')
# sanitize
import re
t = re.sub(r'[^\w\s-]', '', t).strip().replace(' ', '_')[:80]
print(t)
" 2>/dev/null)
  [[ -n "$title" ]] && dest="$OUT/videos/${vid_id}_${title}.mp4"

  echo "downloading $(basename "$dest")"
  curl -sSL --retry 3 --retry-delay 2 \
    -o "$dest" \
    "$mp4_url"
done
echo "  Done."
echo ""

# ── Summary ───────────────────────────────────────────────────────────────────
pdf_count=$(find "$OUT/pdfs"   -name "*.pdf" 2>/dev/null | wc -l | tr -d ' ')
img_count=$(find "$OUT/images" -name "*"     2>/dev/null | wc -l | tr -d ' ')
vid_count=$(find "$OUT/videos" -name "*.mp4" 2>/dev/null | wc -l | tr -d ' ')
total_size=$(du -sh "$OUT" 2>/dev/null | cut -f1)

echo "=== Complete ==="
echo "  PDFs:   $pdf_count"
echo "  Images: $img_count"
echo "  Videos: $vid_count"
echo "  Total size: $total_size"
echo "  Location: $OUT"
