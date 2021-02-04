import sys
import os
from typing import List, Dict, Set
from collections import Counter, OrderedDict
import sqlite3
import csv
import io
import multiprocessing

FLOWLINE_COMID = 0
FLOWLINE_REACHCODE = 1
FLOWLINE_LEVEL = 2
FLOWLINE_ORDER = 3
FLOWLINE_DIVERGENCE = 4

MAIN_STEM_LABEL_BASE_STR = '0'
MAIN_STEM_LABEL_BASE_INT = 0
MAX_MAIN_STEM_NUM = 255
MAX_FIRST_ORDER_NUM = 255
MAX_LEVEL_LABEL = 99
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


def get_downstream_flowlines(flowline, plusflow, comid: int):
    downstream_flowlines = []
    plusflow.execute('select tocomid from plusflow where fromcomid=? order by tocomid asc', (comid,))
    for row in plusflow:
        f = get_flowline(flowline, row[0])
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


def find_root_flowlines(flowline, plusflow, huc8: str, curr_flowline: Flowline,
                        root_flowlines: set=set(), visited: set=set()) -> Flowline:
    visited.add(curr_flowline)
    # print("\tfind_root_flowline: {0}".format(curr_flowline))
    downstream = get_downstream_flowlines(flowline, plusflow, curr_flowline.comid)
    for d in downstream:
        # print("\t\tdownstream: {0}".format(d))
        if d.reachcode.startswith(huc8):
            # Downstream flowline is in the same watershed, keep searching downstream...
            if d not in visited:
                find_root_flowlines(flowline, plusflow, huc8, d, root_flowlines, visited)
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


def _pad_stream_label(label_in, hierarchy_levels, hierarchy_separator='-', empty_level_indicator='0'):
    segments = label_in.split(hierarchy_separator)
    padded_buff = io.StringIO()
    # Create compact label
    for i, s in enumerate(segments):
        if i == 0:
            padded_buff.write(s)
        else:
            padded_buff.write(f"{int(s):02}")
    padded_label = padded_buff.getvalue()
    # Fill missing hierarchy levels with 0
    padded_label = padded_label.ljust(MAX_LABEL_LEN, '0')
    return padded_label


def _process_stream_segment(flowline_orders: Dict[int, Set[Flowline]], order:int, curr_flowline: Flowline, label:str):
    curr_flowline.label = label
    curr_flowline.hack_order = order
    _add_flowline_to_order_list(flowline_orders, order, curr_flowline)


def _get_next_mainstem_label(order_label_count) -> str:
    assert order_label_count[MAIN_STEM_LABEL_BASE_STR] < MAX_MAIN_STEM_NUM,\
        f"Max main stem label {MAX_MAIN_STEM_NUM} exceeded."
    order_label_count[MAIN_STEM_LABEL_BASE_STR] += 1
    # Return as zero-padded hexadecimal
    return "{0:#0x}".format(order_label_count[MAIN_STEM_LABEL_BASE_STR])[2:].rjust(2, '0')


def _get_next_first_order_label(order_label_count, zeroth_order: str) -> str:
    assert order_label_count[zeroth_order] < MAX_FIRST_ORDER_NUM,\
        f"Max first order label {MAX_FIRST_ORDER_NUM} exceeded."
    order_label_count[zeroth_order] += 1
    # Convert to zero-padded hexadecimal
    first_order = "{0:#0x}".format(order_label_count[zeroth_order])[2:].rjust(2, '0')
    return "{0}{1}".format(zeroth_order, first_order)


def _get_next_nth_order_label(order_label_count, n_plus_oneth_order: str) -> str:
    components = n_plus_oneth_order.split(LEVEL_SEP)
    nth_level_stub = LEVEL_SEP.join(components[:-1]) + LEVEL_SEP
    level_stream_count_label = nth_level_stub + '0'
    order_label_count[level_stream_count_label] += 1
    return nth_level_stub + str(order_label_count[level_stream_count_label])


def _get_next_label_for_next_level(new_order: int, curr_level_label: str, order_label_count: Counter = Counter()) -> str:
    next_level_label = None
    if new_order == 1:
        next_level_label = _get_next_first_order_label(order_label_count, curr_level_label)
    elif new_order > 1:
        # Only add a level to the label hierarchy if new_order is 2nd order tributary or greater
        level_stream_count_label = curr_level_label + LEVEL_SEP + '0'
        order_label_count[level_stream_count_label] += 1
        next_level_label = curr_level_label + LEVEL_SEP + str(order_label_count[level_stream_count_label])
    return next_level_label


def _get_next_label_for_prev_level(new_order: int, curr_level_label: str, order_label_count: Counter = Counter()) -> str:
    assert new_order >= 0, f"_get_next_label_for_prev_level() new_ordder should be > 0, but was {new_order}."
    # print("_determine_label_for_prev_level: curr_level_label: {0}, new_order: {1}".format(curr_level_label, new_order))
    prev_level_label = None
    if new_order == 0:
        prev_level_label = _get_next_mainstem_label(order_label_count)
        # print(f"\tprev_level_label: {prev_level_label}")
    elif new_order == 1:
        prev_level_label = _get_next_first_order_label(order_label_count, curr_level_label[0:2])
    else:
        # new_order > 1
        prev_level_label = _get_next_nth_order_label(order_label_count, curr_level_label)

    # print("\tprev_level_label: {0}".format(prev_level_label))
    return prev_level_label


def _get_next_label_for_curr_level(order: int, curr_level_label: str, order_label_count: Counter = Counter()) -> str:

    assert order >= 0, f"_get_next_label_for_prev_level() new_ordder should be > 0, but was {order}."

    new_label = None
    if order == 0:
        new_label = _get_next_mainstem_label(order_label_count)
    elif order == 1:
        new_label = _get_next_first_order_label(order_label_count, curr_level_label[0:2])
    else:
        # order > 1
        new_label = _get_next_nth_order_label(order_label_count, curr_level_label)

    return new_label


def assign_stream_segment_order(flowline, plusflow, huc8: str,
                                curr_flowline: Flowline, flowline_orders: Dict[int, Set[Flowline]],
                                order=0, label=MAIN_STEM_LABEL_BASE_STR,
                                order_label_count: Counter = Counter(), visit_count: Counter = Counter(), itr_meta={}):
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
                    new_label = label
                    # Proceed upstream, using the same label as we are still at the same level of the hierarchy
                    assign_stream_segment_order(flowline, plusflow, huc8, u, flowline_orders,
                                                order=order, label=new_label,
                                                order_label_count=order_label_count, visit_count=visit_count,
                                                itr_meta=itr_meta)
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
                        new_label = _get_next_label_for_prev_level(new_order, label, order_label_count)
                else:
                    # Upstream flowline has a lower Strahler order. Go up order and level in the label hierarchy
                    new_order = order + 1
                    try:
                        new_label = _get_next_label_for_next_level(new_order, label, order_label_count)
                    except Exception as e:
                        mesg = f"\n\n_determine_label_for_next_level threw Exception: {e} for HUC8 {huc8}, " \
                               f"curr_flowline: {curr_flowline}, order: {order}\n\n"
                        sys.exit(mesg)
                # Continue search on the "upstream" (which may be a divergence) flowline
                assign_stream_segment_order(flowline, plusflow, huc8, u, flowline_orders,
                                            order=new_order, label=new_label,
                                            order_label_count=order_label_count, visit_count=visit_count,
                                            itr_meta=itr_meta)


def label_streams_for_huc8(flowline, plusflow, huc8, ws_code, log) -> OrderedDict:
    flowlines_by_stream_id = OrderedDict()

    # Find watershed outlets (i.e. root flowlines)
    query = "select comid from nhdflowline_network where reachcode like '{huc8}%' and startflag=1 order by comid desc".format(huc8=huc8)
    flowline.execute(query)
    root_flowlines = set()
    for i, feat in enumerate(flowline.fetchall(), 1):
        start_comid = feat[0]
        start_flowline = get_flowline(flowline, start_comid)
        # print("Starting flowline {0} has comid: {1}".format(i, start_flowline.comid))
        find_root_flowlines(flowline, plusflow, huc8, start_flowline, root_flowlines)
    # print("Root flowlines for HUC8 '{0}' are: {1}".format(huc8, root_flowlines))
    # Label streams in watershed
    stream_orders = {}
    order_label_count = Counter()
    iteration_metadata = {}
    # Sort root flowlines by descending comid, descending strahler order, and ascending stream level to ensure
    # consistent traversal across invocations starting with the most downstream flowlines (i.e. highest comid).
    root_flowlines = sorted(root_flowlines, key=lambda f: f.comid, reverse=True)
    root_flowlines = sorted(root_flowlines, key=lambda f: f.strahler_order, reverse=True)
    root_flowlines = sorted(root_flowlines, key=lambda f: f.stream_level)
    for root_flowline in root_flowlines:
        assign_stream_segment_order(flowline, plusflow, huc8, root_flowline, stream_orders,
                                    label=_get_next_mainstem_label(order_label_count),
                                    order_label_count=order_label_count, itr_meta=iteration_metadata)

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
        compact_label = _pad_stream_label(k, MAX_LABEL_LEVEL)
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


WS_DATA = [
    ("AA", "03180004", "Lower Pearl"),
    ("AB", "03180005", "Bogue Chitto"),
    ("AC", "08040202", "Lower Ouachita-Bayou De Loutre"),
    ("AD", "08040205", "Bayou Bartholemew"),
    ("AE", "08040206", "Bayou D'Arbonne"),
    ("AF", "08040207", "Lower Ouachita"),
    ("AG", "08040301", "Lower Red"),
    ("AH", "08040302", "Castor"),
    ("AI", "08040303", "Dugdemona"),
    ("AJ", "08040304", "Little"),
    ("AK", "08040305", "Black"),
    ("AL", "08040306", "Bayou Cocodrie"),
    ("AM", "08050001", "Boeuf"),
    ("AN", "08050002", "Bayou Macon"),
    ("AO", "08050003", "Tensas"),
    ("AP", "08060100", "Lower Mississippi-Natchez"),
    ("AQ", "08070100", "Lower Mississippi-Baton Rouge"),
    ("AR", "08070201", "Bayou Sara-Thompson"),
    ("AS", "08070202", "Amite"),
    ("AT", "08070203", "Tickfaw"),
    ("AU", "08070204", "Lake Maurepas"),
    ("AV", "08070205", "Tangipahoa"),
    ("AW", "08070300", "Lower Grand"),
    ("AX", "08080101", "Atchafalaya"),
    ("AY", "08080102", "Bayou Teche"),
    ("AZ", "08080103", "Vermilion"),
    ("BA", "08080201", "Mermentau Headwaters"),
    ("BB", "08080202", "Mermentau"),
    ("BC", "08080203", "Upper Calcasieu"),
    ("BD", "08080204", "Whisky Chitto"),
    ("BE", "08080205", "West Fork Calcasieu"),
    ("BF", "08080206", "Lower Calcasieu"),
    ("BG", "08090100", "Lower Mississippi-New Orleans"),
    ("BH", "08090201", "Liberty Bayou-Tchefuncta"),
    ("BI", "08090203", "Eastern Louisiana Coastal"),
    ("BJ", "08090301", "East Central Louisiana Coastal"),
    ("BK", "08090302", "West Central Louisiana Coastal"),
    ("BL", "11140201", "McKinney-Posten Bayous"),
    ("BM", "11140202", "Middle Red-Coushatta"),
    ("BN", "11140203", "Loggy Bayou"),
    ("BO", "11140204", "Red Chute"),
    ("BP", "11140205", "Bodcau Bayou"),
    ("BQ", "11140206", "Bayou Pierre"),
    ("BR", "11140207", "Lower Red-Lake Iatt"),
    ("BS", "11140208", "Saline Bayou"),
    ("BT", "11140209", "Black Lake Bayou"),
    ("BU", "11140304", "Cross Bayou"),
    ("BV", "11140306", "Caddo Lake"),
    ("BW", "12010002", "Middle Sabine"),
    ("BX", "12010004", "Toledo Bend Reservoir"),
    ("BY", "12010005", "Lower Sabine"),
    ("BZ", "12040201", "Sabine Lake"),
    ("CA", "12010001", "Upper Sabine"),
    ("CB", "12010003", "Lake Fork"),
]

WS_DATA_DEBUG = [
    ("AA", "03180004", "Lower Pearl"),
    # ("AC", "08040202", "Lower Ouachita-Bayou De Loutre"),
    # ("AD", "08040205", "Bayou Bartholemew"),
    # ("AM", "08050001", "Boeuf"),
    # ("BK", "11140202", "Middle Red-Coushatta"),
    # ("AU", "08070204", "Lake Maurepas"),
    # ("AZ", "08080103", "Vermilion"),
    ("BM", "11140202", "Middle Red-Coushatta"),
    # ("BT", "11140209", "Black Lake Bayou"),
    # ("BX", "12040201", "Sabine Lake"),
]


def do_label_streams_for_huc8(ws):
    print("Begin: do_label_streams_for_huc8 for watershed: {0}".format(ws))

    flowline_conn = sqlite3.connect(os.environ.get('NHD_FLOWLINE', 'NHDFlowline_Network.sqlite'))
    flowline = flowline_conn.cursor()
    plusflow_conn = sqlite3.connect(os.environ.get('NHD_PLUSFLOW', 'NHD_PlusFlow.sqlite'))
    plusflow = plusflow_conn.cursor()

    ws_code = ws[0]
    huc8 = ws[1]

    log_file = f"{OUTPUT_PREFIX}/{ws_code}_{huc8}.txt"
    with open(log_file, 'w', encoding='utf-8') as log:
        flowlines_by_stream_id = label_streams_for_huc8(flowline, plusflow, huc8, ws_code, log)
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


if __name__ == '__main__':
    # Parallel
    with(multiprocessing.Pool(multiprocessing.cpu_count())) as p:
        p.map(do_label_streams_for_huc8, WS_DATA)
    # Synchronous
    # for ws in WS_DATA:
    #     do_label_streams_for_huc8(ws)
