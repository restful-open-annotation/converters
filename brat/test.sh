#!/bin/bash

# Convert example data.

OUTDIR=example-converted

rm -rf "$OUTDIR"

for d in EVEX-PMC EVEX-pubmed; do
    i="example-data/${d}"
    o="$OUTDIR/$d"
    echo "Converting $i to $o ..."
    mkdir -p "$o"
    python brat.py -o "$o" "$i"/*.ann
done
