#!/usr/bin/python

"""A module for parsing source maps, as output by the Closure and
CoffeeScript compilers and consumed by browsers.  See
  http://www.html5rocks.com/en/tutorials/developertools/sourcemaps/
"""

import collections
import json
import sys

SmapState = collections.namedtuple(
    'SmapState', ['dst_line', 'dst_col',
                  'src', 'src_line', 'src_col',
                  'name'])

# Mapping of base64 letter -> integer value.
B64 = dict((c, i) for i, c in
           enumerate('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
                     '0123456789+/'))


def parse_vlq(segment):
    """Parse a string of VLQ-encoded data.

    Returns:
      a list of integers.
    """

    values = []

    cur, shift = 0, 0
    for c in segment:
        val = B64[c]
        # Each character is 6 bits:
        # 5 of value and the high bit is the continuation.
        val, cont = val & 0b11111, val >> 5
        cur += val << shift
        shift += 5

        if not cont:
            # The low bit of the unpacked value is the sign.
            cur, sign = cur >> 1, cur & 1
            if sign:
                cur = -cur
            values.append(cur)
            cur, shift = 0, 0

    if cur or shift:
        raise Exception('leftover cur/shift in vlq decode')

    return values


def parse_vlq_test():
    assert parse_vlq('gqjG') == [100000]
    assert parse_vlq('hqjG') == [-100000]
    assert parse_vlq('DFLx+BhqjG') == [-1, -2, -5, -1000, -100000]
    assert parse_vlq('CEKw+BgqjG') == [1, 2, 5, 1000, 100000]
    assert parse_vlq('/+Z') == [-13295]


def parse_smap(f):
    """Given a file-like object, yield SmapState()s as they are read from it."""

    smap = json.load(f)
    sources = smap['sources']
    names = smap['names']
    mappings = smap['mappings']
    lines = mappings.split(';')

    dst_col, src_id, src_line, src_col, name_id = 0, 0, 0, 0, 0
    for dst_line, line in enumerate(lines):
        segments = line.split(',')
        dst_col = 0
        for segment in segments:
            if not segment:
                continue
            parse = parse_vlq(segment)
            dst_col += parse[0]

            src = None
            name = None
            if len(parse) > 1:
                src_id += parse[1]
                src = sources[src_id]
                src_line += parse[2]
                src_col += parse[3]

                if len(parse) > 4:
                    name_id += parse[4]
                    name = names[name_id]

            assert dst_line >= 0
            assert dst_col >= 0
            assert src_line >= 0
            assert src_col >= 0

            yield SmapState(dst_line, dst_col, src, src_line, src_col, name)



def demo():
    # Simple demo that shows files that most contribute to total size.
    cost = collections.Counter()
    last_state = None
    for state in parse_smap(open(sys.argv[1])):
        if last_state:
            # Note: not sure this is correct -- reread the spec to be sure.
            src = state.src or last_state.src
            if state.dst_line == last_state.dst_line:
                span = state.dst_col - last_state.dst_col
                cost[src] += span
        # print 'out[%d:%d] = %s[%d:%d] %s' % (
        #     state.dst_line+1, state.dst_col,
        #     state.src, state.src_line+1, state.src_col, state.name)
        last_state = state

    for file, bytes in cost.most_common():
        print bytes, file


demo()
