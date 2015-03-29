#!/usr/bin/env python

# brat standoff format support

import sys
import re
import fileinput
import json
import codecs

from collections import defaultdict
from itertools import count
from os import path

DEFAULT_ENCODING='utf-8'

def argparser():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument('-o', '--output', metavar='DIR', default=None,
                        help='Output directory')
    parser.add_argument('-t', '--textdir', metavar='DIR', default=None,
                        help='Text directory')
    parser.add_argument('file', metavar='FILE', nargs='+',
                        help='File(s) to convert')

    return parser

def new_id(prefix, ann_by_id):
    for i in count(1):
        if prefix+str(i) not in ann_by_id:
            return prefix+str(i)

class Annotation(object):
    """Base class for annotations with ID and type."""

    def __init__(self, id_, type_):
        self.id = id_
        self.type = type_

    def get_spans(self, ann_by_id=None):
        """Return list of associated (start, end) spans."""
        raise NotImplementedError

    def verify_text(self, text):
        """Verify reference text for textbound annotations."""
        pass

    def oa_id(self):
        """Return the Open Annotation ID for the annotation."""
        return self.id

    def to_openannotation(self, ann_by_id, target_base):
        raise NotImplementedError

    STANDOFF_RE = None

    @classmethod
    def from_standoff(cls, line):
        if cls.STANDOFF_RE is None:
            raise NotImplementedError
        m = cls.STANDOFF_RE.match(line)
        if not m:
            raise ValueError('Failed to parse "%s"' % line)
        return cls(*m.groups())

class Textbound(Annotation):
    """Textbound annotation representing entity mention or event trigger."""

    def __init__(self, id_, type_, spans, text):
        super(Textbound, self).__init__(id_, type_)
        self.spans = spans
        self.text = text

    def get_spans(self, ann_by_id=None):
        """Return list of associated (start, end) spans."""
        spans = []
        for span in self.spans.split(';'):
            start, end = span.split(' ')
            spans.append((int(start), int(end)))
        return spans

    def verify_text(self, text):
        offset = 0
        for start, end in self.get_spans():
            endoff = offset + (end-start)
            assert text[start:end] == self.text[offset:endoff], \
                'Error: text mismatch: "%s" vs. "%s"' % \
                (text[start:end], self.text[offset:endoff])
            offset = endoff + 1

    def to_openannotation(self, ann_by_id, target_base):
        spans = self.get_spans()
        start, end = spans[0][0], spans[-1][1]
        if len(spans) > 1:
            print >> sys.stderr, 'Warning: flattening span %s to %d-%d' % \
                (self.spans, start, end)
        target = '%s#char=%d,%d' % (target_base, start, end)
        obj = {
            '@id': self.oa_id(),
            '@type': 'oa:Annotation',
            'target': target,
            'body': self.type,
        }
        return [obj]

    STANDOFF_RE = re.compile(r'^(\S+)\t(\S+) (\d+ \d+(?:;\d+ \d+)*)\t(.*)$')

class Relation(Annotation):
    """Typed binary relation annotation."""

    def __init__(self, id_, type_, args):
        super(Relation, self).__init__(id_, type_)
        self.args = args

    def get_spans(self, ann_by_id=None):
        """Return list of associated (start, end) spans."""
        if ann_by_id is None:
            print >> sys.stderr, 'Relation.get_spans: missing ann_by_id'
            return []
        else:
            arg1, arg2 = self.get_args()
            a1, a2 = arg1[1], arg2[1]
            return (ann_by_id[a1].get_spans(ann_by_id) +
                    ann_by_id[a2].get_spans(ann_by_id))

    def get_args(self):
        a1, a2 = self.args.split(' ')
        a1key, a1val = a1.split(':', 1)
        a2key, a2val = a2.split(':', 1)
        return ((a1key, a1val), (a2key, a2val))
    
    def to_openannotation(self, ann_by_id, target_base):
        arg1, arg2 = self.get_args()
        obj = {
            'id': self.oa_id(),
            'pred': self.type,
            'subj': arg1[1],
            'obj': arg2[1],
        }
        return [obj]

    STANDOFF_RE = re.compile(r'^(\S+)\t(\S+) (\S+:\S+ \S+:\S+)$')

class Event(Annotation):
    """Typed, textbound event annotation."""

    def __init__(self, id_, type_, trigger, args):
        super(Event, self).__init__(id_, type_)
        self.trigger = trigger
        self.args = args

    def get_spans(self, ann_by_id=None):
        """Return list of associated (start, end) spans."""
        if ann_by_id is None:
            print >> sys.stderr, 'Event.get_spans: missing ann_by_id'
            return []
        else:
            return ann_by_id[self.trigger].get_spans(ann_by_id)

    def get_args(self):
        return [a.split(':', 1) for a in self.args.split(' ')]        

    def oa_id(self):
        """Return the Open Annotation ID for the annotation."""
        # Events are represented using their triggers only.
        return self.trigger

    def to_openannotation(self, ann_by_id, target_base):
        relations = []
        for key, val in self.get_args():
            rid = new_id('R', ann_by_id)
            ann_by_id[rid] = None # reserve
            obj = {
                '@id': rid,
                '@type': 'oa:Annotation',
                'target': target_base, # TODO: specifics?
                'body' : {
                    'from': self.trigger,
                    'to': ann_by_id[val].oa_id(),
                    'label': key,
                }
            }
            relations.append(obj)
        return relations

    STANDOFF_RE = re.compile(r'^(\S+)\t(\S+):(\S+) (\S+:\S+ ?)*$')

class Normalization(Annotation):
    """Reference relating annotation to external resource."""

    def __init__(self, id_, type_, arg, ref, text):
        super(Normalization, self).__init__(id_, type_)
        self.arg = arg
        self.ref = ref
        self.text = text

    def get_spans(self, ann_by_id=None):
        """Return list of associated (start, end) spans."""
        if ann_by_id is None:
            print >> sys.stderr, 'Normalization.get_spans: missing ann_by_id'
            return []
        else:
            return ann_by_id[self.arg].get_spans(ann_by_id)

    def to_openannotation(self, ann_by_id, target_base):
        # TODO: attach to annotated textbound rather than generating
        # an independent annotation.
        spans = self.get_spans(ann_by_id)
        start, end = spans[0][0], spans[-1][1]
        target = '%s#char=%d,%d' % (target_base, start, end)
        obj = {
            '@id': self.oa_id(),
            '@type': 'oa:Annotation',
            'target': target,
            'body': { '@id': self.ref },
        }
        return [obj]

    STANDOFF_RE = re.compile(r'^(\S+)\t(\S+) (\S+) (\S+:\S+)\t?(.*)$')

class Attribute(Annotation):
    """Attribute with optional value associated with another annotation."""

    def __init__(self, id_, type_, arg, val):
        super(Attribute, self).__init__(id_, type_)
        self.arg = arg
        self.val = val

    def get_spans(self, ann_by_id=None):
        """Return list of associated (start, end) spans."""
        if ann_by_id is None:
            print >> sys.stderr, 'Attribute.get_spans: missing ann_by_id'
            return []
        else:
            return ann_by_id[self.arg].get_spans(ann_by_id)

    def to_openannotation(self, ann_by_id, target_base):
        # TODO: attach to annotated textbound rather than generating
        # an independent annotation.
        spans = self.get_spans(ann_by_id)
        start, end = spans[0][0], spans[-1][1]
        target = '%s#char=%d,%d' % (target_base, start, end)
        value = self.type + ('=%s'%self.val if self.val is not None else '')
        obj = {
            '@id': self.oa_id(),
            '@type': 'oa:Annotation',
            'target': target,
            'body': value,
        }
        return [obj]

    STANDOFF_RE = re.compile(r'^(\S+)\t(\S+) (\S+) ?(\S*)$')

class Comment(Annotation):
    """Typed free-form text comment associated with another annotation."""

    def __init__(self, id_, type_, arg, text):
        super(Comment, self).__init__(id_, type_)
        self.arg = arg
        self.text = text

    def get_spans(self, ann_by_id=None):
        """Return list of associated (start, end) spans."""
        if ann_by_id is None:
            print >> sys.stderr, 'Comment.get_spans: missing ann_by_id'
        else:
            return ann_by_id[self.arg].get_spans(ann_by_id)

    def to_openannotation(self, ann_by_id, target_base):
        # TODO: consider mapping.
        return []

    def __str__(self):
        return '%s\t%s %s\t%s' % (self.id, self.type, self.arg, self.text)

    STANDOFF_RE = re.compile(r'^(\S+)\t(\S+) (\S+)\t(.*)$')

def parse_standoff_line(line):
    if not line:
        return None
    elif line[0] == 'T':
        return Textbound.from_standoff(line)
    elif line[0] == 'R':
        return Relation.from_standoff(line)
    elif line[0] == 'E':
        return Event.from_standoff(line)
    elif line[0] == 'N':
        return Normalization.from_standoff(line)
    elif line[0] in ('A', 'M'):
        return Attribute.from_standoff(line)
    elif line[0] == '#':
        return Comment.from_standoff(line)
    else:
        print >> sys.stderr, 'Warning: discarding unrecognized line:', line

def parse_standoff(source):
    annotations = []
    for line in source:
        line = line.rstrip('\n')
        if line.strip() == '':
            continue
        annotations.append(parse_standoff_line(line))
    return annotations

def oa_collection(graph=None):
    if graph is None:
        graph = []
    return {
        '@context': 'http://nlplab.org/ns/restoa-context-20150307.json',
        '@graph': graph
    }

def to_openannotation(annotations, target_base, options=None):
    ann_by_id = { a.id: a for a in annotations }
    openann = []
    for a in annotations:
        openann.extend(a.to_openannotation(ann_by_id, target_base))
    return oa_collection(openann)

def prettyprint_json(obj, ascii=False):
    ppargs = { 'sort_keys': True, 'indent': 2, 'separators': (',', ': ') }
    if ascii:
        # default, returns ASCII with escapes
        return json.dumps(obj, **ppargs)
    else:
        # Unicode
        return json.dumps(obj, ensure_ascii=False, **ppargs)

def find_texts(annotations, options=None):
    if options.textdir is not None:
        dirs = options.textdir
    else:
        dirs = [path.dirname(fn) for fn in annotations]
    base = path.basename(annotations[0])
    textbase = path.splitext(base)[0] + '.txt'
    candidates = [path.join(d, textbase) for d in dirs]
    return [fn for fn in candidates if path.exists(fn)]

def annotations_and_text(filenames, options=None):
    annotations, texts = [], []
    for fn in filenames:
        root, ext = path.splitext(path.basename(fn))
        if ext in ('.txt',):
            texts.append(fn)
        else:
            annotations.append(fn)
    if len(texts) == 0:
        texts = find_texts(annotations, options)
        assert texts != [], 'Failed to find text for %s' % str(annotations)
    if len(texts) > 1:
        print >> sys.stderr, 'Warning: multiple texts for %s' % str(annotations)
    return annotations, texts[0]

def verify_text(annotations, text):
    for a in annotations:
        a.verify_text(text)

def output_text(text, basename, options=None):
    if options is None or options.output is None:
        print >> sys.stdout, text.encode('utf-8')
    else:
        outfn = path.join(options.output, basename)+'.txt'
        with codecs.open(outfn, 'wt', encoding=DEFAULT_ENCODING) as out:
            out.write(text)

def output_oa(collection, basename, options=None):
    if options is None or options.output is None:
        print >> sys.stdout, prettyprint_json(collection).encode('utf-8')
    else:
        outfn = path.join(options.output, basename)+'.jsonld'
        with codecs.open(outfn, 'wt', encoding=DEFAULT_ENCODING) as out:
            out.write(prettyprint_json(collection))

def process_files(files, options=None):
    annfiles, textfile = annotations_and_text(files, options)
    basename = path.splitext(path.basename(textfile))[0]
    standoff = parse_standoff(fileinput.input(annfiles))
    text = codecs.open(textfile, encoding=DEFAULT_ENCODING).read()
    verify_text(standoff, text)
    collection = to_openannotation(standoff, basename+'.txt', options)
    output_text(text, basename, options)
    output_oa(collection, basename, options)
    
def group_files(filenames):
    files_by_basename = defaultdict(list)
    for fn in filenames:
        root, ext = path.splitext(path.basename(fn))
        files_by_basename[root].append(fn)
    return files_by_basename.values()

def main(argv):
    args = argparser().parse_args(argv[1:])

    for group in group_files(args.file):
        process_files(group, args)

    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
