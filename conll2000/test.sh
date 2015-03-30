#!/bin/bash

# Convert example data.

OUTDIR=example-converted

rm -rf "$OUTDIR"

for d in sample.conll; do
    i="example-data/$d"
    o="$OUTDIR"
    echo "Converting $i to $o ..."
    mkdir -p "$o"
    python conll2000.py -o "$o" "$i"
done
