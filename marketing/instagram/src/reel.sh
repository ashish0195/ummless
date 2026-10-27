#!/bin/sh
# Builds reels/one-minute.mp4 (1080 × 1920, H.264, 30 fps, about 10.5 s, silent) from reels/frames/1–5.png:
# 2.5 s per frame with half-second crossfades. Add music in Instagram; trending audio reaches more people.
# Usage, from marketing/instagram after rendering:  npm run reel
set -eu
cd "$(dirname "$0")/.."

HOLD=2.5
FADE=0.5
inputs=""
for n in 1 2 3 4 5; do
  inputs="$inputs -loop 1 -framerate 30 -t $HOLD -i reels/frames/$n.png"
done

# Each crossfade starts FADE seconds before the previous clip ends: offsets 2, 4, 6 and 8 s.
# shellcheck disable=SC2086
ffmpeg -y -loglevel error $inputs -filter_complex "
  [0][1]xfade=transition=fade:duration=$FADE:offset=2[a];
  [a][2]xfade=transition=fade:duration=$FADE:offset=4[b];
  [b][3]xfade=transition=fade:duration=$FADE:offset=6[c];
  [c][4]xfade=transition=fade:duration=$FADE:offset=8,format=yuv420p[v]" \
  -map "[v]" -r 30 -c:v libx264 -profile:v high -crf 18 -movflags +faststart reels/one-minute.mp4

echo "reels/one-minute.mp4"
