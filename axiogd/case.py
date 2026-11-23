"""Load a design case from its agent/ and evaluator/ directories.

The agent/ directory contains the simple and detailed requests and the existing
part description. The evaluator/ directory contains facts for clarification,
reference conditions for scoring, and case metadata.
"""
import json
import re
from pathlib import Path

LEVELS = ('simple', 'detailed')
BANNED_BRIEF_TERMS = ['preserve', 'obstacle', 'load case', 'boundary condition', 'fixed support',
                      'design space', 'objective', 'starting shape', 'constraint', 'constrain',
                      'intrude', 'keep-out', 'keep out']
ROLE_TERMS = ['preserve', 'keep', 'kept', 'must', 'fixed', 'support', 'load', 'obstacle', 'constraint']
AVAILABILITY = ('given', 'derivable', 'ask')
STATUSES = ('explicit', 'derived', 'assumed', 'missing')


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


class Case:
    """Read one case from the directory supplied by the caller."""

    def __init__(self, root):
        self.root = Path(root)
        self.requests = {lvl: _read(self.root / 'agent' / f'request_{lvl}.json') for lvl in LEVELS}
        self.existing_part = _read(self.root / 'agent' / 'existing_part.json')
        self.facts = _read(self.root / 'evaluator' / 'facts.json')
        self.gold = _read(self.root / 'evaluator' / 'gold.json')
        self.meta = _read(self.root / 'evaluator' / 'case_meta.json')
        self.case_id = self.meta['case_id']

    def agent_view(self, level):
        """Return the selected request and geometry as the initial design input."""
        return {'request': self.requests[level], 'existing_part': self.existing_part}

    def input_ids(self, level):
        return {s['id'] for s in self.requests[level]} | {f['id'] for f in self.existing_part}

    def askable_fact_ids(self, level):
        """Facts the agent can only obtain by asking at this level."""
        ids = set()
        for g in self.gold:
            if g['kind'] == 'content' and g['availability'][level] == 'ask':
                ids |= set(g['facts'])
        return ids


def _term_pattern(term):
    """Match a term and its plural or inflected last word: obstacles, constraints, preserved, loaded."""
    words = term.split()
    last = words[-1]
    variants = {last, last + 's', last + 'es', last + 'd', last + 'ed', last + 'ing'}
    if last.endswith('e'):
        variants |= {last[:-1] + 'ing', last[:-1] + 'ed'}
    tail = '(?:' + '|'.join(re.escape(v) for v in sorted(variants, key=len, reverse=True)) + ')'
    head = ''.join(re.escape(w) + r'\s+' for w in words[:-1])
    return r'\b' + head + tail + r'\b'


def _has_term(text, term):
    return re.search(_term_pattern(term), text, flags=re.IGNORECASE) is not None


def _numbers(text):
    return set(re.findall(r'\d+(?:\.\d+)?', text))


def check_case(case):
    """Check the structure and wording of case files."""
    from .contract import CATEGORIES

    problems = []
    if case.case_id != case.root.name:
        problems.append(f'case_id {case.case_id} does not match the folder name {case.root.name}')
    for kind, ids in (('fact', [k['id'] for k in case.facts]), ('gold', [g['id'] for g in case.gold])):
        if len(ids) != len(set(ids)):
            problems.append(f'{kind} IDs must be unique')
    for lvl in LEVELS:
        ids = [s['id'] for s in case.requests[lvl]]
        if len(ids) != len(set(ids)) or not all(re.fullmatch(r'N\d+', i) for i in ids):
            problems.append(f'{lvl}: request IDs must be unique N#')
        for s in case.requests[lvl]:
            for term in BANNED_BRIEF_TERMS:
                if _has_term(s['text'], term):
                    problems.append(f"{lvl} {s['id']}: GD term '{term}' in the request")
    simple, detailed = case.requests['simple'], case.requests['detailed']
    if detailed[:len(simple)] != simple:
        problems.append('detailed request must start with the simple sentences, unchanged')
    fids = [f['id'] for f in case.existing_part]
    if len(fids) != len(set(fids)) or not all(re.fullmatch(r'F\d+', i) for i in fids):
        problems.append('existing-part IDs must be unique F#')
    for f in case.existing_part:
        for term in ROLE_TERMS:
            if _has_term(f['text'], term):
                problems.append(f"{f['id']}: role word '{term}' in the existing-part data")
    fact_ids = {k['id'] for k in case.facts}
    for k in case.facts:
        if not k.get('topic', '').strip() or not k.get('answer', '').strip():
            problems.append(f"{k['id']}: fact needs topic and answer")
        for term in BANNED_BRIEF_TERMS:
            if _has_term(k.get('answer', ''), term):
                problems.append(f"{k['id']}: GD term '{term}' in the designer's answer")
        for lvl in LEVELS:
            unknown = set(k['revealed_in'][lvl]) - {s['id'] for s in case.requests[lvl]}
            if unknown:
                problems.append(f"{k['id']}: revealed_in {lvl} has unknown IDs {sorted(unknown)}")
    simple_text = ' '.join(s['text'] for s in simple)
    for k in case.facts:
        if not k['revealed_in']['simple']:
            leaked = _numbers(k['answer']) & _numbers(simple_text)
            if leaked:
                problems.append(f"{k['id']}: simple request contains its values {sorted(leaked)}")
    for g in case.gold:
        if g['category'] not in CATEGORIES:
            problems.append(f"{g['id']}: unknown category {g['category']}")
        if g['kind'] == 'content':
            if not g['facts'] or not set(g['facts']) <= fact_ids:
                problems.append(f"{g['id']}: content element needs existing facts")
            for lvl in LEVELS:
                av = g['availability'][lvl]
                if av not in AVAILABILITY:
                    problems.append(f"{g['id']}: availability {av} for {lvl}")
                revealed = any(k['revealed_in'][lvl] for k in case.facts if k['id'] in g['facts'])
                if av == 'ask' and revealed:
                    problems.append(f"{g['id']}: marked ask at {lvl} but its fact is in the request")
                if not set(g['statuses'][lvl]) <= set(STATUSES):
                    problems.append(f"{g['id']}: invalid statuses for {lvl}")
        elif g['kind'] != 'freedom':
            problems.append(f"{g['id']}: kind must be content or freedom")
    return problems
