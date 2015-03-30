#!/bin/bash

# Convert the CRAFT corpus 1.0 Knowtator annotations into the Open
# Annotation format.

set -e
set -u

if [ "$#" -lt 2 -o "$#" -gt 2 ]; then
    echo "Usage: $0 CRAFT-ROOT OUTPUT-DIR"
    exit 1
fi

indir="$1/knowtator-xml"
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

for d in "$indir"/*; do
    n=$(basename "$d")
    od="$outdir/$n"
    mkdir -p "$od"
    for f in "$d"/*; do
	o="$od"/$(basename "$f" .txt.knowtator.xml).jsonld
	echo "Converting $f into $o ..." >&2
	./knowtator2oa.py -e -d "$textdir" "$f" > "$o"
    done
done