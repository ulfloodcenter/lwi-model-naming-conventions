# Copyright (C) 2021-present State of Louisiana, Division of Administration, Office of Community Development.
# All rights reserved. Licensed under the GPLv3 License. See LICENSE.txt in the project root for license information.

import sys
from typing import Tuple, List, Dict, Set, Callable
from collections import Counter, OrderedDict
import sqlite3
import csv
import io
import multiprocessing
import argparse

import base32_crockford as b32

FLOWLINE_COMID = 0
FLOWLINE_REACHCODE = 1
FLOWLINE_LEVEL = 2
FLOWLINE_ORDER = 3
FLOWLINE_DIVERGENCE = 4

MAIN_STEM_LABEL_BASE_STR = '0'
MAIN_STEM_LABEL_BASE_INT = 0
MAX_MAIN_STEM_NUM = 255
MAX_MAIN_STEM_NUM_B32 = 1023
MAX_FIRST_ORDER_NUM = 255
MAX_FIRST_ORDER_NUM_B32 = 1023
MAX_LEVEL_LABEL = 255
MAX_LEVEL_LABEL_B32 = 1023
LEVEL_SEP = '-'

MAX_LABEL_LEN = 14
MAX_FQ_LABEL_LEN = 16
MAX_LABEL_LEVEL = 6

OUTPUT_PREFIX = 'output'


class Flowline:
    def __init__(self, comid, reachcode, stream_level, strahler_order, divergence, hack_order=None, label=''):
        self.comid = comid
        self.reachcode = reachcode
        self.stream_level = stream_level
        self.strahler_order = strahler_order
        self.divergence = divergence
        self.hack_order = hack_order
        self.label = label

    def __str__(self):
        return f"Flowline(comid={self.comid}, reachcode={self.reachcode}, stream_level={self.stream_level}, " \
               f"strahler_order={self.strahler_order}, divergence={self.divergence}, " \
               f"hack_order={self.hack_order}, label={self.label})"

    def __repr__(self):
        return self.__str__()

    def __eq__(self, o: object) -> bool:
        if not isinstance(o, Flowline):
            raise NotImplemented()
        if self.comid != o.comid:
            return False
        if self.reachcode != o.reachcode:
            return False
        if self.stream_level != o.stream_level:
            return False
        if self.strahler_order != o.strahler_order:
            return False
        if self.divergence != o.divergence:
            return False
        if self.hack_order != o.hack_order:
            return False
        if self.label != o.label:
            return False
        return True

    def __hash__(self) -> int:
        return hash(self.comid) + hash(self.reachcode) + hash(self.stream_level) + hash(self.strahler_order) + \
            hash(self.divergence) + hash(self.hack_order) + hash(self.label)


def get_flowline(cur, comid: int):
    cur.execute('select comid, reachcode, streamleve, streamorde, divergence from nhdflowline_network where comid=?',
                (comid,))
    f = cur.fetchone()
    if f is None:
        return f
    return Flowline(comid=f[FLOWLINE_COMID], reachcode=f[FLOWLINE_REACHCODE], stream_level=f[FLOWLINE_LEVEL],
                    strahler_order=f[FLOWLINE_ORDER], divergence=f[FLOWLINE_DIVERGENCE])


def get_flowline_hr(cur, nhdplusid: float):
    cur.execute(('select fl.nhdplusid, fl.reachcode, vaa.streamleve, vaa.streamorde, vaa.divergence '
                 'from nhdflowline as fl, nhdplusflowlinevaa as vaa '
                 'where fl.nhdplusid=? and fl.nhdplusid=vaa.nhdplusid'),
                (nhdplusid,))
    f = cur.fetchone()
    if f is None:
        return f
    return Flowline(comid=f[FLOWLINE_COMID], reachcode=f[FLOWLINE_REACHCODE], stream_level=f[FLOWLINE_LEVEL],
                    strahler_order=f[FLOWLINE_ORDER], divergence=f[FLOWLINE_DIVERGENCE])


def get_headwater_reaches(flowline: sqlite3.Cursor, huc8: str) -> Callable[[None], List]:
    def curried():
        query = "select comid from nhdflowline_network where reachcode like '{huc8}%' and startflag=1 order by comid desc".format(
            huc8=huc8)
        flowline.execute(query)
        return flowline.fetchall()
    return curried


def get_headwater_reaches_hr(flowline: sqlite3.Cursor, huc8: str) -> Callable[[None], List]:
    def curried():
        query = "select nhdplusid from nhdplusflowlinevaa where reachcode like '{huc8}%' and startflag=1".format(
            huc8=huc8)
        flowline.execute(query)
        return flowline.fetchall()
    return curried


def get_downstream_flowlines(flowline, plusflow, comid: int):
    downstream_flowlines = []
    plusflow.execute('select tocomid from plusflow where fromcomid=? order by tocomid asc', (comid,))
    for row in plusflow:
        f = get_flowline(flowline, row[0])
        if f:
            downstream_flowlines.append(f)
    return downstream_flowlines


def get_downstream_flowlines_hr(nhdplushr, nhdplusid: float):
    downstream_flowlines = []
    nhdplushr.execute('select tonhdpid from nhdplusflow where fromnhdpid=?', (nhdplusid,))
    for row in nhdplushr:
        f = get_flowline_hr(nhdplushr, row[0])
        if f:
            downstream_flowlines.append(f)
    return downstream_flowlines


def get_upstream_flowlines(flowline, plusflow, comid: int):
    upstream_flowlines = []
    plusflow.execute('select fromcomid from plusflow where tocomid=? order by fromcomid desc', (comid,))
    for row in plusflow:
        f = get_flowline(flowline, row[0])
        if f:
            upstream_flowlines.append(f)
    return upstream_flowlines


def get_upstream_flowlines_hr(nhdplushr, nhdplusid: float):
    upstream_flowlines = []
    nhdplushr.execute('select fromnhdpid from nhdplusflow where tonhdpid=?', (nhdplusid,))
    for row in nhdplushr:
        f = get_flowline_hr(nhdplushr, row[0])
        if f:
            upstream_flowlines.append(f)
    return upstream_flowlines


def find_root_flowlines(flowline, plusflow, huc8: str, curr_flowline: Flowline,
                        root_flowlines: set = set(), visited: set = set(), nhd_hr: bool = False) -> Flowline:
    visited.add(curr_flowline)
    # print("\tfind_root_flowline: {0}".format(curr_flowline))

    if curr_flowline.stream_level == 1.0:
        # Current flowline terminates on the coastline, add as a root flowline, don't search "downstream"
        root_flowlines.add(curr_flowline)
    else:
        if nhd_hr:
            downstream = get_downstream_flowlines_hr(flowline, curr_flowline.comid)
        else:
            downstream = get_downstream_flowlines(flowline, plusflow, curr_flowline.comid)
        for d in downstream:
            # print("\t\tdownstream: {0}".format(d))
            if d.reachcode.startswith(huc8):
                # Downstream flowline is in the same watershed, keep searching downstream...
                if d not in visited:
                    find_root_flowlines(flowline, plusflow, huc8, d, root_flowlines, visited, nhd_hr)
            else:
                # Downstream flowline is not in the same watershed, curr_flowline is a root flowline
                # in the watershed.
                root_flowlines.add(curr_flowline)


def _add_flowline_to_order_list(flowline_orders: Dict[int, Set[Flowline]], order, flowline):
    flowlines_for_order = None
    try:
        flowlines_for_order = flowline_orders[order]
    except KeyError:
        flowlines_for_order = set()
        flowline_orders[order] = flowlines_for_order
    flowlines_for_order.add(flowline)


def _int_to_hex_str(num: int) -> str:
    return "{0:#0x}".format(num)[2:].rjust(2, '0')


def _pad_stream_label(label_in, hierarchy_levels, hierarchy_separator='-', empty_level_indicator='0',
                      base32: bool = False):
    segments = label_in.split(hierarchy_separator)
    padded_buff = io.StringIO()
    # Create compact label
    for i, s in enumerate(segments):
        if i == 0:
            if base32:
                # Convert hexadecimal to base32 (this is a hack, we should go back to just storing decimal not hex)
                label = b32.encode(int(s, base=16)).rjust(2, '0')
            else:
                # Emit name as hexadecimal
                label = s
            padded_buff.write(label)
        else:
            if base32:
                label = b32.encode(s)
            else:
                # Convert 2nd and higher orders to hexadecimal here
                label = _int_to_hex_str(int(s))
            padded_buff.write(label)
    padded_label = padded_buff.getvalue()
    # Fill missing hierarchy levels with 0
    padded_label = padded_label.ljust(MAX_LABEL_LEN, '0')
    return padded_label


def _process_stream_segment(flowline_orders: Dict[int, Set[Flowline]], order:int, curr_flowline: Flowline, label:str):
    curr_flowline.label = label
    curr_flowline.hack_order = order
    _add_flowline_to_order_list(flowline_orders, order, curr_flowline)


def _get_next_mainstem_label(order_label_count, base32: bool = False) -> str:
    if base32:
        max_main_stem = MAX_MAIN_STEM_NUM_B32
    else:
        max_main_stem = MAX_MAIN_STEM_NUM
    assert order_label_count[MAIN_STEM_LABEL_BASE_STR] < max_main_stem,\
        f"Max main stem label {max_main_stem} exceeded."
    order_label_count[MAIN_STEM_LABEL_BASE_STR] += 1
    # Return as zero-padded hexadecimal
    return "{0:#0x}".format(order_label_count[MAIN_STEM_LABEL_BASE_STR])[2:].rjust(2, '0')


def _get_next_first_order_label(order_label_count, zeroth_order: str, base32: bool = False) -> str:
    if base32:
        max_first_order = MAX_FIRST_ORDER_NUM_B32
    else:
        max_first_order = MAX_FIRST_ORDER_NUM
    assert order_label_count[zeroth_order] < max_first_order,\
        f"Max first order label {max_first_order} exceeded."
    order_label_count[zeroth_order] += 1
    # Convert to zero-padded hexadecimal
    first_order = "{0:#0x}".format(order_label_count[zeroth_order])[2:].rjust(2, '0')
    return "{0}{1}".format(zeroth_order, first_order)


def _get_next_nth_order_label(order_label_count, n_plus_oneth_order: str, base32: bool = False) -> str:
    if base32:
        max_nth_order = MAX_LEVEL_LABEL_B32
    else:
        max_nth_order = MAX_LEVEL_LABEL

    components = n_plus_oneth_order.split(LEVEL_SEP)
    nth_level_stub = LEVEL_SEP.join(components[:-1]) + LEVEL_SEP
    level_stream_count_label = nth_level_stub + '0'

    assert order_label_count[level_stream_count_label] < max_nth_order, \
        f"Max first order label {max_nth_order} exceeded."

    order_label_count[level_stream_count_label] += 1
    return nth_level_stub + str(order_label_count[level_stream_count_label])


def _get_next_label_for_next_level(new_order: int, curr_level_label: str, order_label_count: Counter = Counter(),
                                   base32: bool = False) -> str:
    next_level_label = None
    if new_order == 1:
        next_level_label = _get_next_first_order_label(order_label_count, curr_level_label, base32)
    elif new_order > 1:
        # Only add a level to the label hierarchy if new_order is 2nd order tributary or greater
        level_stream_count_label = curr_level_label + LEVEL_SEP + '0'
        order_label_count[level_stream_count_label] += 1
        next_level_label = curr_level_label + LEVEL_SEP + str(order_label_count[level_stream_count_label])
    return next_level_label


def _get_next_label_for_prev_level(new_order: int, curr_level_label: str, order_label_count: Counter = Counter(),
                                   base32: bool = False) -> str:
    assert new_order >= 0, f"_get_next_label_for_prev_level() new_ordder should be > 0, but was {new_order}."
    # print("_determine_label_for_prev_level: curr_level_label: {0}, new_order: {1}".format(curr_level_label, new_order))
    prev_level_label = None
    if new_order == 0:
        prev_level_label = _get_next_mainstem_label(order_label_count, base32)
        # print(f"\tprev_level_label: {prev_level_label}")
    elif new_order == 1:
        prev_level_label = _get_next_first_order_label(order_label_count, curr_level_label[0:2], base32)
    else:
        # new_order > 1
        prev_level_label = _get_next_nth_order_label(order_label_count, curr_level_label, base32)

    # print("\tprev_level_label: {0}".format(prev_level_label))
    return prev_level_label


def _get_next_label_for_curr_level(order: int, curr_level_label: str, order_label_count: Counter = Counter(),
                                   base32: bool = False) -> str:

    assert order >= 0, f"_get_next_label_for_prev_level() new_ordder should be > 0, but was {order}."

    new_label = None
    if order == 0:
        new_label = _get_next_mainstem_label(order_label_count, base32)
    elif order == 1:
        new_label = _get_next_first_order_label(order_label_count, curr_level_label[0:2], base32)
    else:
        # order > 1
        new_label = _get_next_nth_order_label(order_label_count, curr_level_label, base32)

    return new_label


def assign_stream_segment_order(flowline, plusflow, huc8: str,
                                curr_flowline: Flowline, flowline_orders: Dict[int, Set[Flowline]],
                                order=0, label=MAIN_STEM_LABEL_BASE_STR,
                                order_label_count: Counter = Counter(), visit_count: Counter = Counter(), itr_meta={},
                                nhd_hr: bool = False, base32: bool = False):
    # print("assign_stream_segment_order: curr_flowline: {0}".format(curr_flowline))
    if visit_count[curr_flowline.comid] > 0:
        # Don't process a flowline more than once
        return
    else:
        visit_count[curr_flowline.comid] += 1

    itr_meta['max_order'] = max(itr_meta.get('max_order', 0), order)

    # Record the current flowline
    _process_stream_segment(flowline_orders, order, curr_flowline, label)
    # Search upstream for additional reaches of this branch, or additional tributaries
    if nhd_hr:
        upstream = get_upstream_flowlines_hr(flowline, curr_flowline.comid)
    else:
        upstream = get_upstream_flowlines(flowline, plusflow, curr_flowline.comid)
    for u in upstream:
        # print("\tupstream: {0}".format(u))
        if not u.reachcode.startswith(huc8):
            # The upstream segment is not in this watershed, skip this segment.
            continue
        else:
            # Upstream flowline is in this watershed
            if u.strahler_order == curr_flowline.strahler_order:
                # Upstream flowline is of the same order as current flowline, add to list of flowlines for this
                # order
                if curr_flowline.divergence > 1:
                    if u.divergence != curr_flowline.divergence:
                        # The current flowline is a minor flowpath of a divergence, but the "upstream" flowline is either
                        # not on a divergence (divergence=0), or is the major flowpath of a divergence (divergence=1).
                        # In these cases, we don't want to recurse upstream from the minor flowpath as this will result
                        # in a spurious level in the hierarchy being created.
                        # print("assign_stream_segment_order(): curr_flowline.divergence == 2 and u.divergence != curr_flowline.divergence")
                        continue
                    if u.stream_level < curr_flowline.stream_level:
                        # The current flowline is a minor flowpath of a divergence and has a stream level higher
                        # than the "upstream" flowline (this can happen in cases of compound divergent flow).
                        # this means that the upstream flowline is closer to being on the mainstem than the current
                        # flowline, so we don't want to propagate upstream from here as despite having the same Stahler
                        # orders, the current divergence flowline is further derived from the main stem than the
                        # upstream flowline (we want the upstream flowline to be named named from another reach
                        # downstream of it that is closer to being on the main stem).
                        continue
                else:
                    if u.divergence > 1:
                        # Upstream flowline is a minor flowpath of a divergence, create a new label at the current
                        # level in the hierarchy instead of carrying the current label upstream. This will avoid
                        # there being two parallel segments with the same name, which can be problematic for models
                        # such as HEC-RAS.
                        new_label = _get_next_label_for_curr_level(order, label, order_label_count, base32)
                    else:
                        # Proceed upstream, using the same label as we are still at the same level of the hierarchy
                        # new_order = order
                        new_label = label
                    assign_stream_segment_order(flowline, plusflow, huc8, u, flowline_orders,
                                                order=order, label=new_label,
                                                order_label_count=order_label_count, visit_count=visit_count,
                                                itr_meta=itr_meta,
                                                nhd_hr=nhd_hr, base32=base32)
            else:
                # Upstream flowline is not of the same order as the current flowline
                new_order = None
                new_label = None
                if u.strahler_order > curr_flowline.strahler_order:
                    # "Upstream" flowline has a higher Strahler order than the current flowline.
                    # This can happen in areas with divergent flow. Go down an order and level in the label
                    # hierarchy
                    if order == 0:
                        new_order = order
                        new_label = label
                    else:
                        new_order = order - 1
                        new_label = _get_next_label_for_prev_level(new_order, label, order_label_count, base32)
                else:
                    # Upstream flowline has a lower Strahler order. Go up order and level in the label hierarchy
                    new_order = order + 1
                    try:
                        new_label = _get_next_label_for_next_level(new_order, label, order_label_count, base32)
                    except Exception as e:
                        mesg = f"\n\n_determine_label_for_next_level threw Exception: {e} for HUC8 {huc8}, " \
                               f"curr_flowline: {curr_flowline}, order: {order}\n\n"
                        sys.exit(mesg)
                # Continue search on the "upstream" (which may be a divergence) flowline
                assign_stream_segment_order(flowline, plusflow, huc8, u, flowline_orders,
                                            order=new_order, label=new_label,
                                            order_label_count=order_label_count, visit_count=visit_count,
                                            itr_meta=itr_meta,
                                            nhd_hr=nhd_hr, base32=base32)


def label_streams_for_huc8(flowline, plusflow, headwater_reaches, huc8, ws_code, log,
                           nhd_hr: bool = False, base32: bool = False) -> OrderedDict:
    flowlines_by_stream_id = OrderedDict()

    # Find watershed outlets (i.e. root flowlines)
    root_flowlines = set()
    for i, feat in enumerate(headwater_reaches(), 1):
        start_comid = feat[0]
        if nhd_hr:
            start_flowline = get_flowline_hr(flowline, start_comid)
        else:
            start_flowline = get_flowline(flowline, start_comid)
        # print("Starting flowline {0} has comid: {1}".format(i, start_flowline.comid))
        find_root_flowlines(flowline, plusflow, huc8, start_flowline, root_flowlines, nhd_hr=nhd_hr)
    # print("Root flowlines for HUC8 '{0}' are: {1}".format(huc8, root_flowlines))
    # Label streams in watershed
    stream_orders = {}
    order_label_count = Counter()
    iteration_metadata = {}
    # Sort root flowlines by descending reachcode, descending strahler order, ascending stream level to ensure
    # consistent traversal across invocations starting with the most downstream flowlines (i.e. highest reachcode).
    # Also sort by divergence to make sure the first flowline isn't a minor flowpath of a divergence.
    # Doesn't seem to make sense to sort NHDPlusHR flow lines by NHDPlusID as it doesn't seem to vary predictably
    # downstream
    root_flowlines = sorted(root_flowlines, key=lambda f: f.reachcode, reverse=True)
    root_flowlines = sorted(root_flowlines, key=lambda f: f.strahler_order, reverse=True)
    root_flowlines = sorted(root_flowlines, key=lambda f: f.stream_level)
    root_flowlines = sorted(root_flowlines, key=lambda f: f.divergence)
    log.write(f"DEBUG: len(root_flowlines): {len(root_flowlines)}\n")
    for root_flowline in root_flowlines:
        assign_stream_segment_order(flowline, plusflow, huc8, root_flowline, stream_orders,
                                    label=_get_next_mainstem_label(order_label_count, base32),
                                    order_label_count=order_label_count, itr_meta=iteration_metadata,
                                    nhd_hr=nhd_hr, base32=base32)

    log.write(f"Statistics for Watershed {ws_code}, HUC8 '{huc8}'...\n")

    # Store stream labels in a dictionary with key=label and value=list of flowlines with that label
    # (super inefficient)
    raw_flowlines_by_stream_id = {}
    for o in stream_orders.keys():
        for f in stream_orders[o]:
            flowlines_with_id = None
            try:
                flowlines_with_id = raw_flowlines_by_stream_id[f.label]
            except KeyError:
                flowlines_with_id = []
                raw_flowlines_by_stream_id[f.label] = flowlines_with_id
            flowlines_with_id.append(f)
    # Now sort by ID, reformat IDs to contain the full hierarchy, and convert to compact form
    # without delimiters
    label_depth = iteration_metadata['max_order']
    log.write(f"\tMax depth was: {label_depth}\n")
    max_compact_length = 0
    for k in sorted(raw_flowlines_by_stream_id.keys()):
        compact_label = _pad_stream_label(k, MAX_LABEL_LEVEL, base32=base32)
        # print(f"compact_label: {compact_label}")
        max_compact_length = max(max_compact_length, len(compact_label))
        flowlines_by_stream_id[compact_label] = raw_flowlines_by_stream_id[k]
    log.write(f"\tMax compact label length was {max_compact_length}\n")

    # Calculate statistics on the number of streams in each order
    num_reaches_per_order = [0] * (label_depth + 2)
    for k in order_label_count:
        if k == MAIN_STEM_LABEL_BASE_STR:
            num_reaches_per_order[0] = order_label_count[k]
        else:
            c = k.split(LEVEL_SEP)
            num_reaches_per_order[len(c)] = order_label_count[k]
    for i, count in enumerate(num_reaches_per_order):
        log.write(f"\tNum streams of order {i}: {count}\n")

    return flowlines_by_stream_id


def load_watersheds_data(ws_filepath: str) -> List[Tuple[str, str, str]]:
    watersheds = []
    with open(ws_filepath, 'r') as csvfile:
        ws_reader = csv.DictReader(csvfile)
        for ws in ws_reader:
            watersheds.append((ws['WS_code'], ws['HUC8'], ws['Name']))
    return watersheds


def do_label_streams_for_huc8(ws: Tuple[str, str, str], flowline_path: str, plusflow_path: str,
                              nhd_hr: bool = False, base32: bool = False):
    print("Begin: do_label_streams_for_huc8 for watershed: {0}".format(ws))

    flowline_conn = sqlite3.connect(flowline_path)
    flowline = flowline_conn.cursor()
    plusflow = None
    if not nhd_hr:
        plusflow_conn = sqlite3.connect(plusflow_path)
        plusflow = plusflow_conn.cursor()

    ws_code = ws[0]
    huc8 = ws[1]

    log_file = f"{OUTPUT_PREFIX}/{ws_code}_{huc8}.txt"
    with open(log_file, 'w', encoding='utf-8') as log:
        if nhd_hr:
            flowlines_by_stream_id = label_streams_for_huc8(flowline, plusflow,
                                                            get_headwater_reaches_hr(flowline, huc8),
                                                            huc8, ws_code, log, nhd_hr, base32)
        else:
            flowlines_by_stream_id = label_streams_for_huc8(flowline, plusflow,
                                                            get_headwater_reaches(flowline, huc8),
                                                            huc8, ws_code, log, nhd_hr, base32)
        # Save results as CSV
        outfile = f"{OUTPUT_PREFIX}/{ws_code}_{huc8}.csv"
        with open(outfile, 'w') as csvfile:
            fieldnames = ['stream_label', 'ws_code', 'huc8', 'comid', 'reachcode', 'divergence']
            w = csv.DictWriter(csvfile, delimiter=',', quotechar='"', fieldnames=fieldnames)
            w.writeheader()
            for k in flowlines_by_stream_id.keys():
                flowlines = flowlines_by_stream_id[k]
                for f in flowlines:
                    label = f"{ws_code}{k}"
                    label_len = len(label)
                    if label_len > MAX_FQ_LABEL_LEN:
                        log.write(f"!!! WARNING: Stream label {label} has length {label_len}, which is longer than the max length of {MAX_FQ_LABEL_LEN}\n")
                    w.writerow({
                        'stream_label': f"{ws_code}{k}",
                        'ws_code': ws_code,
                        'huc8': huc8,
                        'comid': f.comid,
                        'reachcode': f.reachcode,
                        'divergence': f.divergence
                    })

    print("Finish: do_label_streams_for_huc8 for watershed: {0}".format(ws))


def parallel_do_label_streams_for_huc8(args):
    # Can't pickle a curried function so we'll do this instead
    do_label_streams_for_huc8(*args)


def main():
    parser = argparse.ArgumentParser(description='LWI Stream Naming Convention Example code')
    parser.add_argument('-f', '--flowline', required=True,
                        help=('Path to SQLite file containing NHDPlus flowline geometries. '
                              'If NHDPlus HR is specified, the SQLite file must also contain '
                              'NHDPlusFlowlineVAA, and NHDPlusFlow.'))
    parser.add_argument('-p', '--plusflow',
                        help=('Path to SQLite file containing NHDPlus PlusFlow table. '
                              'Only required if NHDPlus HR is NOT specified.'))
    parser.add_argument('-w', '--watersheds', type=str, default='input/LWI_watersheds.csv',
                        help=('Path to CSV file containing watershed definitions that controls the '
                              'HUC8 watersheds whose NHD flowlines are to be labeled.'))
    parser.add_argument('-n', '--num_threads', type=int, default=multiprocessing.cpu_count(),
                        help=('Number of threads to use to process watersheds. '
                              f"Defaults to {multiprocessing.cpu_count()} on this machine."))
    parser.add_argument('--nhdhr', action='store_true', help='Use NHDPlus HR', default=False)
    parser.add_argument('--base32', action='store_true',
                        help='Encode stream reach IDs as Crockford base32 instead of hexadecimal. Default: True',
                        default=True)
    parser.add_argument('--hexadecimal', action='store_true',
                        help='Encode stream reach IDs as hexadecimal instead of Crockford base32. Default: False',
                        default=False)
    args = parser.parse_args()

    flowline_path = args.flowline
    plusflow_path = None
    if args.plusflow:
        plusflow_path = args.plusflow

    use_base32 = False
    if args.base32 and not args.hexadecimal:
        use_base32 = True

    # Load watershed data
    ws_data = load_watersheds_data(args.watersheds)

    if args.num_threads > 1:
        # Parallel
        with(multiprocessing.Pool(args.num_threads)) as p:
            par_args = [(ws, flowline_path, plusflow_path, args.nhdhr, use_base32) for ws in ws_data]
            p.map(parallel_do_label_streams_for_huc8, par_args)
    else:
        # Synchronous
        for ws in ws_data:
            do_label_streams_for_huc8(ws, flowline_path, plusflow_path, args.nhdhr, args.base32)


if __name__ == '__main__':
    main()
