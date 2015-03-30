#!/bin/bash

# Convert example data.

OUTDIR=example-converted

rm -rf "$OUTDIR"

for d in 11532192 12546709 15314659 15328533 15588329 15938754 16507151 17244351; do
    i="example-data/$d.txt.knowtator.xml"
    o="$OUTDIR"
    echo "Converting $i to $o ..."
    mkdir -p "$o"
    python knowtator.py -o "$o" "$i"
done
