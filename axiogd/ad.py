"""Schemas and checks for the intermediate Axiomatic Design (AD) records.

These records capture requirements and their clarification, functional
requirements (FRs) and design parameters (DPs), and the decomposition review.
The validation functions return warnings for the run log. The method uses
blocking issues from the review to decide whether to revise a decomposition.
"""
from .contract import CATEGORIES, canon
from .jsonschema_lite import STR, STRS, obj

AD_CATEGORIES = ['CN', 'FR', 'C', 'nFR', 'OC', 'SC', 'GIVEN_PHYSICAL', 'OPERATING_CONDITION',
                 'EXPLICIT_FREEDOM', 'MISSING_INPUT']
GD_TARGETS = CATEGORIES + ['none']
DP_STATUSES = ['given', 'hypothesis', 'placeholder', 'solver_delegated']
CHECK_TOPICS = ['hierarchy', 'fr_separation', 'dp_status', 'derived_conditions', 'missing_information']

AD_REQ_SCHEMA = obj({
    'artifact_and_boundary': STR,
    'items': {'type': 'array', 'items': obj({
        'item_id': STR, 'category': {'type': 'string', 'enum': AD_CATEGORIES}, 'statement': STR,
        'origin': {'type': 'string', 'enum': ['explicit', 'derived']},
        'data_status': {'type': 'string', 'enum': ['complete', 'missing', 'not_applicable']},
        'linked_ids': STRS, 'evidence': STRS,
        'gd_target': {'type': 'string', 'enum': GD_TARGETS},
        'maps_directly': {'type': ['boolean', 'null']},
        'decision_note': STR})},
    'questions': {'type': 'array', 'items': obj({'item_ids': STRS, 'text': STR})}})

DECOMP_SCHEMA = obj({
    'hierarchy_decision': STR,
    'fr_nodes': {'type': 'array', 'items': obj({
        'id': STR, 'parent_id': {'type': ['string', 'null']}, 'statement': STR,
        'source_item_ids': STRS, 'why_at_this_level': STR})},
    'dp_nodes': {'type': 'array', 'items': obj({
        'id': STR, 'for_fr_id': STR, 'physical_candidate': STR,
        'status': {'type': 'string', 'enum': DP_STATUSES}, 'evidence_needed': STR})},
    'derived_conditions': {'type': 'array', 'items': obj({
        'id': STR, 'gd_target': {'type': 'string', 'enum': GD_TARGETS}, 'statement': STR,
        'status': {'type': 'string', 'enum': ['derived', 'hypothesis']}, 'premises': STRS})},
    'matrix_fr_ids': STRS, 'matrix_dp_ids': STRS,
    'matrix_cells': {'type': 'array', 'items': obj({
        'fr_id': STR, 'dp_id': STR, 'influence': {'type': 'string', 'enum': ['yes', 'no', 'unknown']},
        'reason': STR})},
    'independence_status': {'type': 'string', 'enum': ['undetermined', 'uncoupled', 'decoupled', 'coupled']},
    'independence_reason': STR,
    'formulation_blockers': STRS,
    'req_corrections': {'type': 'array', 'items': obj({'item_id': STR, 'correction': STR})}})

AD_REQ_UPDATE_SCHEMA = obj({'updated_items': {'type': 'array',
                                             'items': AD_REQ_SCHEMA['properties']['items']['items']}})

CHECK_SCHEMA = obj({
    'verdict': {'type': 'string', 'enum': ['PASS', 'REVISE']},
    'checks': {'type': 'array', 'items': obj({
        'topic': {'type': 'string', 'enum': CHECK_TOPICS},
        'judgment': {'type': 'string', 'enum': ['pass', 'revise', 'uncertain']}, 'evidence': STR})},
    'issues': {'type': 'array', 'items': obj({
        'issue_id': STR, 'severity': {'type': 'string', 'enum': ['blocking', 'advisory']},
        'affected_ids': STRS, 'problem': STR, 'revision_request': STR})},
    'closure': {'type': 'array', 'items': obj({
        'prior_issue_id': STR, 'closed': {'type': 'boolean'}, 'note': STR})}})


def validate_ad_req(req, input_ids):
    warnings = []
    ids = [i['item_id'] for i in req['items']]
    known = set(ids)
    if len(ids) != len(known):
        warnings.append('AD-REQ item IDs are not unique')
    cn = {i['item_id'] for i in req['items'] if i['category'] == 'CN'}
    for i in req['items']:
        if i['category'] == 'FR':
            if not set(i['linked_ids']) & cn:
                warnings.append(f"{i['item_id']}: FR is not linked to a CN")
            if not isinstance(i['maps_directly'], bool):
                warnings.append(f"{i['item_id']}: FR needs maps_directly true or false")
        elif i['maps_directly'] is not None:
            warnings.append(f"{i['item_id']}: maps_directly must be null for non-FR items")
        unknown = [e for e in i['evidence'] if canon(e) not in input_ids]
        if unknown:
            warnings.append(f"{i['item_id']}: unknown evidence {unknown}")
        unknown_links = [x for x in i['linked_ids'] if x not in known]
        if unknown_links:
            warnings.append(f"{i['item_id']}: unknown linked_ids {unknown_links}")
    for n, q in enumerate(req['questions'], 1):
        unknown = [x for x in q['item_ids'] if x not in known]
        if unknown:
            warnings.append(f'question {n}: unknown item_ids {unknown}')
    if len(req['questions']) > 10:
        warnings.append(f"{len(req['questions'])} questions; only the first 10 are asked")
    return warnings


def validate_decomp(dec, req, decompose_fr_ids):
    warnings = []
    frs = {f['id']: f for f in dec['fr_nodes']}
    if len(frs) != len(dec['fr_nodes']):
        warnings.append('duplicate FR node IDs')
    req_ids = {i['item_id'] for i in req['items']}
    for f in dec['fr_nodes']:
        if f['parent_id'] is not None and f['parent_id'] not in frs:
            warnings.append(f"{f['id']}: unknown parent {f['parent_id']}")
        unknown = [x for x in f['source_item_ids'] if x not in req_ids]
        if unknown:
            warnings.append(f"{f['id']}: unknown source_item_ids {unknown}")
    covered = {x for f in dec['fr_nodes'] for x in f['source_item_ids']}
    for fr in decompose_fr_ids:
        if fr not in covered:
            warnings.append(f'{fr}: listed for decomposition but not traced by any FR node')
    dp_ids = {d['id'] for d in dec['dp_nodes']}
    for d in dec['dp_nodes']:
        if d['for_fr_id'] not in frs:
            warnings.append(f"{d['id']}: unknown for_fr_id {d['for_fr_id']}")
    if sum(d['status'] == 'solver_delegated' for d in dec['dp_nodes']) > 1:
        warnings.append('more than one solver_delegated DP; the layout must not be split')
    rows, cols = dec['matrix_fr_ids'], dec['matrix_dp_ids']
    if rows or cols:
        if not set(rows) <= set(frs) or not set(cols) <= dp_ids:
            warnings.append('matrix rows or columns reference unknown nodes')
        if len({frs[r]['parent_id'] for r in rows if r in frs}) > 1:
            warnings.append('matrix FR rows are not siblings')
        pairs = {(c['fr_id'], c['dp_id']) for c in dec['matrix_cells']}
        if pairs != {(r, c) for r in rows for c in cols}:
            warnings.append('matrix cells do not cover every row-column pair exactly')
    for c in dec['req_corrections']:
        if c['item_id'] not in req_ids:
            warnings.append(f"req_corrections: unknown item {c['item_id']}")
    return warnings


def validate_check(chk, prior_issue_ids=None):
    warnings = []
    if sorted(c['topic'] for c in chk['checks']) != sorted(CHECK_TOPICS):
        warnings.append('checks must cover each of the five topics once')
    blocking = [i for i in chk['issues'] if i['severity'] == 'blocking']
    if (chk['verdict'] == 'REVISE') != bool(blocking):
        warnings.append('verdict does not match the blocking issues; the blocking issues decide')
    if prior_issue_ids:
        closed_ids = {c['prior_issue_id'] for c in chk['closure']}
        missing = [i for i in prior_issue_ids if i not in closed_ids]
        if missing:
            warnings.append(f'closure is missing for prior issues {missing}')
    return warnings


def ad_ids(req, dec=None, checks=()):
    ids = {i['item_id'] for i in req['items']}
    if dec:
        ids |= {f['id'] for f in dec['fr_nodes']} | {d['id'] for d in dec['dp_nodes']}
        ids |= {c['id'] for c in dec['derived_conditions']}
    for chk in checks or ():
        ids |= {i['issue_id'] for i in chk['issues']}
    return ids


def merge_req(req, update):
    """Apply AD-REQ-UPDATE: returned items replace same-id items or are appended. Returns (merged, warnings)."""
    items = [dict(i) for i in req['items']]
    index = {i['item_id']: n for n, i in enumerate(items)}
    for item in update['updated_items']:
        if item['item_id'] in index:
            items[index[item['item_id']]] = dict(item)
        else:
            index[item['item_id']] = len(items)
            items.append(dict(item))
    returned = {i['item_id'] for i in update['updated_items']}
    warnings = [f"{i['item_id']}: FR not reassessed after the answers; its earlier maps_directly is kept"
                for i in req['items'] if i['category'] == 'FR' and i['item_id'] not in returned]
    return dict(req, items=items), warnings
