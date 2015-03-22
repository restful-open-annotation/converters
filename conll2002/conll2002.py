#!/usr/bin/env python

"""CoNLL 2002 shared task format support."""

__author__ = 'Sampo Pyysalo'
__license__ = 'MIT'

import sys
import re
import os
import codecs
import json

INPUT_ENCODING = "Latin-1"
OUTPUT_ENCODING = "UTF-8"

def argparser():
    import argparse
    parser = argparse.ArgumentParser(description="Convert CoNLL'02 data.")
    parser.add_argument('-o', '--output', metavar='DIR', default=None,
                        help='Output directory.')
    parser.add_argument('-f', '--format', choices=['oa', 'ann'], default='oa',
                        help='Output format.')
    parser.add_argument('file', nargs='+', help='Source file(s).')
    return parser

class Standoff(object):
    def __init__(self, id_, type_, start, end, text):
        self.id = id_
        self.type = type_
        self.start = start
        self.end = end
        self.text = text
        self.validate()

    def to_oa(self, docpath):
        """Convert Standoff to Open Annotation."""
        # Assume Web Annotation WG context
        annotation = {
            '@id': str(self.id),
            '@type': 'oa:Annotation',
            'target': docpath + '#char=%d,%d' % (self.start, self.end),
            'body': self.type
        }
        return annotation

    def validate(self):
        # sanity checks
        assert '\n' not in self.text, "ERROR: newline in span '%s'" % \
            (self.text)
        assert self.text == self.text.strip(), \
            "ERROR: span contains extra whitespace: '%s'" % (self.text)

    def __unicode__(self):
        return "T%d\t%s %d %d\t%s" % \
            (self.id, self.type, self.start, self.end, self.text)

def is_quote(s):
    return s in ('"', )

def include_space(t1, t2, quote_count = None):
    # Helper for reconstructing sentence text. Given the text of two
    # consecutive tokens, returns a heuristic estimate of whether a
    # space character should be placed between them.
    if re.match(r'^[\(]$', t1):
        return False
    if re.match(r'^[.,\)\?\!]$', t2):
        return False
    if is_quote(t1) and quote_count is not None and quote_count % 2 == 1:
        return False
    if is_quote(t2) and quote_count is not None and quote_count % 2 == 1:
        return False
    return True

def output_filenames(dir, infn, docnum, suffix):
    outfn = os.path.join(dir, os.path.basename(infn)+'-doc-'+str(docnum))
    return outfn+'.txt', outfn+'.'+suffix

def prettyprint(doc):
    """Pretty-print JSON document."""
    return json.dumps(doc, sort_keys=True, indent=2, separators=(',', ': '))

def write_ann(textout, annout, text, standoffs):
    for so in standoffs:
        print >> annout, unicode(so)
    print >> textout, text
write_ann.suffix = 'ann'

def write_oa(textout, annout, text, standoffs):
    document = {
        '@context': 'http://nlplab.org/ns/restoa-context-20150307.json',
        '@graph': []
    }
    for so in standoffs:
        document['@graph'].append(so.to_oa(os.path.basename(textout.name)))
    print >> annout, prettyprint(document)
    print >> textout, text
write_oa.suffix = 'jsonld'

def make_output_function(directory, basename, writer):
    """Return function that invokes the writer with text and standoffs."""
    def output(text, standoffs):
        if directory is None:
            writer(sys.stdout, sys.stdout, text, standoffs)
        else:
            txtfn, sofn = output_filenames(directory, basename, output.docnum,
                                           writer.suffix)
            with codecs.open(txtfn, 'wt', encoding=OUTPUT_ENCODING) as txtf:
                with codecs.open(sofn, 'wt', encoding=OUTPUT_ENCODING) as sof:
                    writer(txtf, sof, text, standoffs)
        output.docnum += 1
    output.docnum = 1
    return output

def text_and_standoffs(sentences):
    """Convert (token, tag, type) sequences into text and Standoffs."""
    offset, idnum = 0, 1
    doctext = ""
    standoffs = []

    for si, sentence in enumerate(sentences):
        prev_token = None
        prev_tag = "O"
        curr_start, curr_type = None, None
        quote_count = 0

        for token, ttag, ttype in sentence:
            if curr_type is not None and (ttag != "I" or ttype != curr_type):
                # a previously started tagged sequence does not
                # continue into this position.
                text = doctext[curr_start:offset]
                so = Standoff(idnum, curr_type, curr_start, offset, text)
                standoffs.append(so)
                idnum += 1
                curr_start, curr_type = None, None

            if (prev_token is not None and 
                include_space(prev_token, token, quote_count)):
                doctext = doctext + ' '
                offset += 1

            if curr_type is None and ttag != "O":
                # a new tagged sequence begins here
                curr_start, curr_type = offset, ttype

            doctext = doctext + token
            offset += len(token)

            if is_quote(token):
                quote_count += 1

            prev_token = token
            prev_tag = ttag
        
        # leftovers?
        if curr_type is not None:
            text = doctext[curr_start:offset]
            so = Standoff(idnum, curr_type, curr_start, offset, text)
            standoffs.append(so)
            idnum += 1

        if si+1 != len(sentences):
            doctext = doctext + '\n'        
            offset += 1

    return doctext, standoffs
            
def lookahead(iterable, distance=1):
    """Yield tuples of current item and next items from iterable."""
    # modified from https://github.com/maaku/lookahead/
    iterator = iter(iterable)
    # Fill initial
    items = [iterator.next()]
    for i in range(distance):
        try:
            items.append(iterator.next())
        except StopIteration:
            items.append(None)
            distance -= 1
    # Main loop
    for i in iterator:
        yield tuple(items)
        items = items[1:] + [i]
    # Pad with None
    for i in range(distance+1):
        yield tuple(items)
        items = items[1:] + [None]
    raise StopIteration

def is_sentence_break(line):
    # blank lines separate sentences
    return re.match(r'^\s*$', line)

def is_document_break(line):
    # special character sequence separating documents
    return re.match(r'^===*\s+O\s*$', line) or re.match(r'^-DOCSTART-', line)

def is_post_document_break(line, next_line, next_next_line):
    # Heuristic match for likely doc break before current sentence.
    # Note: this doesn't add a break at the current sentence, but
    # before it. (See e.g. line 278 in esp.train)
    return (next_next_line is not None and
            re.match(r'^\s*$', next_line) and
            re.match(r'^-+\s+O\s*$', next_next_line))

def parse_token_line(line):
    # The format for spanish is is word and BIO tag separated by
    # space, and for dutch word, POS and BIO tag separated by
    # space. Try both.
    m = re.match(r'^(\S+)\s(\S+)$', line)
    if not m:
        m = re.match(r'^(\S+)\s\S+\s(\S+)$', line)
    assert m, "Error parsing line: %s" % line
    return m.groups()

def parse_tag(tag):
    m = re.match(r'^([BIO])((?:-[A-Za-z_]+)?)$', tag)
    assert m, "ERROR: failed to parse tag '%s' in %s" % (tag, fn)
    ttag, ttype = m.groups()
    if len(ttype) > 0 and ttype[0] == "-":
        ttype = ttype[1:]
    return ttag, ttype

def _parse_conll(source):
    # Implementation for parse_conll() don't invoke directly.
    # Store (token, BIO-tag, type) triples for sentence 
    sentences = []
    current = []
    # We need lookahead for the document break heuristic.
    for ln, next_three_lines in enumerate(lookahead(source, 2)):
        line, l2, l3 = next_three_lines
        line = line.strip()

        if is_sentence_break(line):
            sentences.append(current)
            current = []
            continue

        if is_document_break(line):
            yield sentences
            sentences = []
            continue

        if is_post_document_break(line, l2, l3):
            yield sentences
            sentences = []
            # Go on to process current token normally

        # Normal line.
        token, tag = parse_token_line(line)
        ttag, ttype = parse_tag(tag)
        current.append((token, ttag, ttype))

    # Process leftovers, if any
    sentences.append(current)
    yield sentences

def parse_conll(source):
    """Parse CoNLL 2002 data, yield documents in (token, tag, type) format."""
    for sentences in _parse_conll(source):
        # Filter out empty sentences and documents, yield nonempties.
        sentences = [s for s in sentences if len(s) > 0]
        if len(sentences) > 0:
            yield sentences

def convert_conll(source, callback):
    """Convert CoNLL 2002 data, invoke callback with text and standoffs."""
    for sentences in parse_conll(source):
        text, standoffs = text_and_standoffs(sentences)
        callback(text, standoffs)

def select_writer(args):
    if args.format == 'oa':
        return write_oa
    elif args.format == 'ann':
        return write_ann
    else:
        assert False, 'internal error'

def main(argv):
    # Take an optional "-o" arg specifying an output directory for the results
    args = argparser().parse_args(argv[1:])
    writer = select_writer(args)
    for fn in args.file:
        output = make_output_function(args.output, fn, writer)
        with codecs.open(fn, encoding=INPUT_ENCODING) as f:
            convert_conll(f, output)
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv))
