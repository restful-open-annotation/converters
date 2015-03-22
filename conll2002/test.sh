#!/bin/bash

# Convert example data.

OUTDIR=example-converted

rm -rf "$OUTDIR"

for d in esp ned; do
    i="example-data/$d.train"
    o="$OUTDIR/$d"    
    echo "Converting $i to $o ..."
    mkdir -p "$o"
    python conll2002.py -o "$o" "$i"
done
