#!/bin/sh
# run_all BUILD CAND_DIR RUNS_DIR [NAME]
#
# Run every driver of one build over every candidate file in CAND_DIR: cases.tsv with hbdrv into RUNS_DIR/NAME.out,
# and each <drv>.tsv with its API driver into RUNS_DIR/NAME.<drv>.out. NAME defaults to BUILD (a second name lets
# the same build run again, as the repeated base runs do). Runs inside the pipeline image only.
set -u
B=/work/out/hb/$1
C=$2
R=$3
N=${4:-$1}
sh /pipe/run_cases.sh "$B" hbdrv "$C/cases.tsv" "$R/$N.out"
for f in "$C"/*.tsv; do
  d=$(basename "$f" .tsv)
  [ "$d" = cases ] && continue
  case $d in
    api) prog=hbapi ;;
    meta) prog=hbmeta ;;
    api*) prog=hb$d ;;
    *) continue ;;
  esac
  sh /pipe/run_cases.sh "$B" "$prog" "$f" "$R/$N.$d.out"
done
