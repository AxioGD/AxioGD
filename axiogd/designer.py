"""Answer clarification questions using the case's recorded facts.

The matching model sees question text and fact topics, but not the answers.
The program assembles replies from the matched facts' fixed answer texts.
Matching details stay in the log; the formulation method receives only
answer IDs, question text and answer text.
"""
from .jsonschema_lite import STR, obj

CAP = 10
UNSPECIFIED = 'No specific requirement; use your engineering judgment.'
TOO_BROAD = 'Please ask about a specific aspect.'
PARTIAL_REST = 'For the other points you asked about: no specific requirement; use your engineering judgment.'
SCHEMA_NAME = 'designer_matcher_v1'


def matcher_schema(fact_ids, question_ids):
    """Restrict matching to the facts and questions in this clarification round."""
    aspect = obj({'aspect': STR,
                  'fact_ids': {'type': 'array', 'items': {'type': 'string', 'enum': list(fact_ids)}},
                  'kind': {'type': 'string', 'enum': ['specific', 'unspecified']}})
    return obj({'matches': {'type': 'array', 'items': obj({
        'question_id': {'type': 'string', 'enum': list(question_ids)},
        'too_broad': {'type': 'boolean'},
        'aspects': {'type': 'array', 'items': aspect}})}})


def number_questions(raw_questions):
    """Assign Q1, Q2, ... in order; retain excess questions in the log only."""
    numbered = [dict(q, id=f'Q{i}') for i, q in enumerate(raw_questions, 1)]
    return numbered[:CAP], numbered[CAP:]


def matcher_user(questions, facts):
    """Expose fact IDs and topics to the matcher, without the answer texts."""
    return {'questions': [{'id': q['id'], 'text': q['text']} for q in questions],
            'facts': [{'id': f['id'], 'topic': f['topic']} for f in facts]}


def assemble(questions, matcher_answer, facts):
    """Return fixed-text answers and warnings from the matcher's selections.

    Ai answers Qi. Matched facts are deduplicated and joined in case-file
    order. Unmatched aspects and broad questions use the protocol's fixed
    replies. Missing or inconsistent matches produce warnings in the log.
    """
    by_id = {f['id']: f for f in facts}
    order = [f['id'] for f in facts]
    found, answers, warnings = {}, [], []
    for m in matcher_answer.get('matches', []):
        if m['question_id'] in found:
            warnings.append(f"matcher listed {m['question_id']} more than once; the first entry is used")
        else:
            found[m['question_id']] = m
    for index, q in enumerate(questions, 1):
        match = found.get(q['id'])
        if match is None:
            warnings.append(f"matcher returned nothing for {q['id']}; answered as unspecified")
            match = {'too_broad': False, 'aspects': []}
        aspects = []
        for a in match['aspects']:
            ids, kind = [fid for fid in order if fid in set(a['fact_ids'])], a['kind']
            if kind == 'specific' and not ids:
                warnings.append(f"{q['id']}: aspect '{a['aspect']}' is specific without facts; treated as unspecified")
                kind = 'unspecified'
            if kind == 'unspecified' and ids:
                warnings.append(f"{q['id']}: aspect '{a['aspect']}' is unspecified but lists facts {ids}; facts ignored")
                ids = []
            aspects.append({'aspect': a['aspect'], 'fact_ids': ids, 'kind': kind})
        ids = [fid for fid in order if any(fid in a['fact_ids'] for a in aspects)]
        if ids:
            kind, text = 'specific', ' '.join(by_id[fid]['answer'] for fid in ids)
            if any(a['kind'] == 'unspecified' for a in aspects):
                text += ' ' + PARTIAL_REST
        elif match['too_broad']:
            kind, text = 'too_broad', TOO_BROAD
        else:
            kind, text = 'unspecified', UNSPECIFIED
        answers.append({'id': f'A{index}', 'question_id': q['id'], 'question': q['text'], 'answer': text,
                        'kind': kind, 'fact_ids': ids, 'aspects': aspects,
                        'asked_by': q.get('record_id') or q.get('item_ids')})
    unknown = sorted(set(found) - {q['id'] for q in questions})
    if unknown:
        warnings.append(f'matcher returned unknown question IDs {unknown}')
    return answers, warnings


def public_answers(answers):
    """Return answer IDs, questions and replies, omitting internal match details."""
    return [{'id': a['id'], 'question': a['question'], 'answer': a['answer']} for a in answers]


def run_designer(session, prompts, raw_questions, facts):
    """Run one clarification round and return (answers, log).

    Ask the matcher once at low reasoning effort.
    With no questions, return an empty record without a model call.
    """
    asked, overflow = number_questions(raw_questions)
    log = {'questions': asked, 'overflow': overflow, 'matcher': None, 'answers': [], 'warnings': []}
    if not asked:
        return [], log
    match = session.ask('DESIGNER-MATCH', prompts['designer_matcher'], matcher_user(asked, facts),
                        SCHEMA_NAME, matcher_schema([f['id'] for f in facts], [q['id'] for q in asked]),
                        effort='low')
    log['matcher'] = match
    log['answers'], log['warnings'] = assemble(asked, match, facts)
    return log['answers'], log
