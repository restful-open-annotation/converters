#!/bin/bash

# Convert example data.

OUTDIR=example-converted

rm -rf "$OUTDIR"

for d in de es fr hu sv cs en fi ga it; do
    i="example-data/${d}-sample.conllu"
    o="$OUTDIR"
    echo "Converting $i to $o ..."
    mkdir -p "$o"
    python conllu.py -o "$o" "$i"
done
