#!/bin/bash

# Convert the CRAFT corpus 1.0 treebank annotations into the Open
# Annotation format.

set -e
set -u

if [ "$#" -lt 2 -o "$#" -gt 2 ]; then
    echo "Usage: $0 CRAFT-ROOT OUTPUT-DIR"
    exit 1
fi

indir="$1/treebank"
textdir="$1/articles/txt"
outdir="$2"

if [ ! -d "$indir" ]; then
    echo "$indir: not a directory"
    exit 1
fi

if [ ! -d "$textdir" ]; then
    echo "$textdir: not a directory"
    exit 1
fi

if [ -e "$outdir" ]; then
    echo "$outdir exists, won't clobber"
    exit 1
fi

mkdir -p "$outdir"

for f in "$indir"/*; do
    o="$outdir"/$(basename "$f" .tree).jsonld
    echo "Converting $f into $o ..." >&2
    ./ptb2oa.py -e -d "$textdir" -a "http://compbio.ucdenver.edu/Hunter_lab" "$f" > "$o"
done
