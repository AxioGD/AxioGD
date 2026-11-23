"""Rules for recording the final generative design (GD) problem formulation.

LLM + GD rules and AxioGD use this format to report established conditions,
open questions, unused GD categories, implementation tasks, and notes. The case
checker also uses the category list when checking the reference conditions
supplied with a case.

Validation checks required fields, coverage of the GD categories, and links to
inputs and supporting records. Engineering correctness is assessed separately.
The runner can use the reported issues to request a correction and merge it
with the original formulation. Readiness flags open conditions marked required.
"""
import re
from copy import deepcopy

from .jsonschema_lite import STR, STRS, obj, validate as schema_validate

VERSION = 'gd-formulation-contract-1.0'
CATEGORIES = ['starting_shape', 'design_space', 'preserve_interfaces', 'obstacle_clearances',
              'load_cases', 'support_conditions', 'allowable_deformation', 'performance_limits',
              'material', 'manufacturing', 'objective']
BLOCKS = ('settled', 'open', 'not_used')
_CAT = {'type': 'string', 'enum': CATEGORIES}
SETTLED = obj({'id': STR, 'category': _CAT, 'item': STR, 'value': STR,
               'status': {'type': 'string', 'enum': ['explicit', 'derived']},
               'evidence': STRS, 'basis': STR, 'ad_refs': STRS})
OPEN = obj({'id': STR, 'category': _CAT, 'item': STR,
            'status': {'type': 'string', 'enum': ['assumed', 'missing']},
            'proposed_value': {'type': ['string', 'null']}, 'required': {'type': 'boolean'},
            'question': STR, 'evidence': STRS, 'basis': STR, 'ad_refs': STRS})
NOT_USED = obj({'id': STR, 'category': _CAT, 'item': STR, 'reason': STR, 'evidence': STRS})
TASK = obj({'task': STR, 'depends_on': STRS})
FINAL_SCHEMA = obj({'settled': {'type': 'array', 'items': SETTLED},
                    'open': {'type': 'array', 'items': OPEN},
                    'not_used': {'type': 'array', 'items': NOT_USED},
                    'execution_tasks': {'type': 'array', 'items': TASK},
                    'notes': STRS})
PATCH_SCHEMA = obj({'settled': {'type': 'array', 'items': SETTLED},
                    'open': {'type': 'array', 'items': OPEN},
                    'not_used': {'type': 'array', 'items': NOT_USED},
                    'remove_ids': STRS})
_INPUT_REF = re.compile(r'^[NFA]\d+$')


def canon(ref):
    """'[n3]', 'N 3' and 'n3' become 'N3'; other IDs keep their case."""
    text = re.sub(r'\s+', '', str(ref).strip().strip('[]()'))
    return text.upper() if re.fullmatch(r'[nNfFaA]\d+', text) else text


def normalize_refs(output):
    """Copy with canonical evidence, ad_refs and depends_on entries, plus the number changed."""
    out, changed = deepcopy(output), 0
    for block in BLOCKS:
        for record in out.get(block, []):
            for field in ('evidence', 'ad_refs'):
                if field in record:
                    new = [canon(r) for r in record[field]]
                    changed += sum(a != b for a, b in zip(new, record[field]))
                    record[field] = new
    for task in out.get('execution_tasks', []):
        old = task.get('depends_on', [])
        new = [canon(r) for r in old]
        changed += sum(a != b for a, b in zip(new, old))
        task['depends_on'] = new
    return out, changed


def record_ids(output):
    found = {}
    for block in BLOCKS:
        for record in output.get(block, []):
            found.setdefault(record['id'], block)
    return found


def _v(rid, rule, problem, fix):
    return {'id': rid, 'rule': rule, 'problem': problem, 'fix': fix}


def validate(output, input_ids, ad_ids=None):
    """Contract violations; empty when valid. input_ids are the canonical N#/F#/A# of this run."""
    issues = schema_validate(output, FINAL_SCHEMA)
    if issues:
        return [_v('(schema)', 'V1', '; '.join(issues[:20]),
                   'Return JSON that follows the supplied schema exactly.')]
    out, seen = [], {}
    for block in BLOCKS:
        for r in output[block]:
            seen.setdefault(r['id'], []).append(block)
    for rid, blocks in seen.items():
        if not rid.strip() or len(blocks) > 1 or _INPUT_REF.match(rid):
            out.append(_v(rid or '(empty)', 'V2', 'record ID is empty, repeated or looks like an input ID',
                          'Give every record a unique, nonempty id that is not of the form N#, F# or A#.'))
    present = {r['category'] for block in BLOCKS for r in output[block]}
    for cat in CATEGORIES:
        if cat not in present:
            out.append(_v('(categories)', 'V3', f'category {cat} does not appear',
                          f'Add a settled, open or not_used record for {cat}.'))
    ids = set(seen)
    settled_ids = {r['id'] for r in output['settled']}
    allowed_ad = set(ad_ids or ())
    for block in BLOCKS:
        for r in output[block]:
            if not r['item'].strip():
                out.append(_v(r['id'], 'V1', 'item is empty', 'Describe the condition in item.'))
            unknown = [e for e in r['evidence'] if e not in input_ids and e not in ids]
            if unknown:
                out.append(_v(r['id'], 'V4', f'unknown evidence IDs {unknown}',
                              'Cite only N#, F#, A# IDs from the inputs or IDs of records in this formulation.'))
            bad_ad = [a for a in r.get('ad_refs', []) if a not in allowed_ad] if ad_ids is not None else []
            if bad_ad:
                out.append(_v(r['id'], 'V4', f'unknown ad_refs {bad_ad}',
                              'Use only IDs that appear in the supplied AD representation.'))
    for r in output['settled']:
        rid, ev = r['id'], r['evidence']
        if not r['value'].strip():
            out.append(_v(rid, 'V1', 'settled value is empty',
                          'Give the established value, or move the record to open.'))
        if r['status'] == 'explicit' and not any(e in input_ids for e in ev):
            out.append(_v(rid, 'V5', 'explicit condition cites no N#, F# or A# input',
                          'Cite the input that states it, or mark it derived with a basis.'))
        if r['status'] == 'derived':
            if not r['basis'].strip() or not ev:
                out.append(_v(rid, 'V6', 'derived condition lacks basis or evidence',
                              'State the premises in evidence and the relationship in basis.'))
            unsettled = [e for e in ev if e in ids and e not in settled_ids]
            if unsettled:
                out.append(_v(rid, 'V6', f'derived condition rests on unsettled records {unsettled}',
                              'Derive only from settled conditions, or move this record to open as assumed.'))
    for r in output['open']:
        if r['status'] == 'assumed' and not (r['proposed_value'] or '').strip():
            out.append(_v(r['id'], 'V7', 'assumed condition has no proposed_value', 'Give the proposed value.'))
        if r['status'] == 'missing' and r['proposed_value'] is not None:
            out.append(_v(r['id'], 'V8', 'missing condition has a proposed_value',
                          'Set proposed_value to null, or mark the record assumed if you propose a value.'))
        if not r['basis'].strip():
            out.append(_v(r['id'], 'V9', 'open condition has an empty basis',
                          'Explain why the condition is needed and open.'))
    for r in output['not_used']:
        if not r['reason'].strip():
            out.append(_v(r['id'], 'V10', 'not_used record has an empty reason',
                          'Explain why the category is not used.'))
    graph = {r['id']: [e for e in r['evidence'] if e in settled_ids]
             for r in output['settled'] if r['status'] == 'derived'}
    if _has_cycle(graph):
        out.append(_v('(derivations)', 'V11', 'derived conditions form a cycle',
                      'Remove the circular reference between derived conditions.'))
    for t in output['execution_tasks']:
        unknown = [d for d in t['depends_on'] if d not in ids]
        if unknown:
            out.append(_v('(execution_tasks)', 'V12', f'task depends on unknown records {unknown}',
                          'Reference only record IDs in this formulation.'))
    return out


def _has_cycle(graph):
    state = {}

    def visit(node):
        if state.get(node) == 1:
            return True
        if state.get(node) == 2:
            return False
        state[node] = 1
        if any(visit(n) for n in graph.get(node, []) if n in graph):
            return True
        state[node] = 2
        return False

    return any(visit(n) for n in graph)


def merge_patch(output, patch):
    """Patch records replace same-id records in any block (or are added); remove_ids deletes."""
    out = deepcopy(output)
    replacing = {r['id'] for block in BLOCKS for r in patch.get(block, [])} | set(patch.get('remove_ids', []))
    for block in BLOCKS:
        out[block] = [r for r in out[block] if r['id'] not in replacing]
    for block in BLOCKS:
        out[block].extend(deepcopy(patch.get(block, [])))
    return out


def readiness(output):
    blocking = [r['id'] for r in output['open'] if r['required']]
    return {'status': 'NEEDS_CLARIFICATION' if blocking else 'READY', 'blocking_ids': blocking}


def questions(output):
    return [{'record_id': r['id'], 'text': r['question'].strip()}
            for r in output.get('open', []) if r.get('question', '').strip()]


def format_violations(violations):
    return '\n'.join(f"- [{v['rule']}] {v['id']}: {v['problem']}. Fix: {v['fix']}" for v in violations)
