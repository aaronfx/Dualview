#!/bin/bash
# renders segments in parallel (4 at a time) and encodes each to mp4, then concats
cd /home/user/Dualview/gopipways-zones/build
export NODE_PATH=$(npm root -g)
W=/tmp/claude-0/gz/seg; mkdir -p $W; rm -rf $W/*
seg() { i=$1; t0=$((i*90)); t1=$(( (i+1)*90 )); d=$W/f$i; mkdir -p $d
  node render_seg.js $d 30 $t0 $t1 > $W/log$i.txt 2>&1
  ffmpeg -y -loglevel error -framerate 30 -i $d/f%05d.jpg -vf "format=yuv420p" -c:v libx264 -preset medium -crf 21 -r 30 -colorspace bt709 -color_primaries bt709 -color_trc bt709 $W/seg$i.mp4 && rm -rf $d; echo done $i >> $W/progress.txt; }
export -f seg; export W
seq 0 11 | xargs -P 4 -I{} bash -c 'seg {}'
for i in $(seq 0 11); do echo "file 'seg$i.mp4'" >> $W/list.txt; done
echo ALLDONE >> $W/progress.txt
