#!/bin/bash

# Convert example data.

OUTDIR=example-converted

rm -rf "$OUTDIR"

for d in 15550985.tree; do
    i="example-data/$d"
    o="$OUTDIR"
    echo "Converting $i to $o ..."
    mkdir -p "$o"
    python ptb.py -o "$o" "$i"
done
