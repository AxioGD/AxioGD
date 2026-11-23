"""Run one case and save its result for one of the three paper methods.

For direct LLM use, the case metadata can supply llm_study_question after the
design request and geometry. Alternatively, prompt_dir can supply the original
messages for that request version (system.txt and user.txt, or initial_messages.json).
The designer may answer clarification requests in the first reply in one follow-up.
For structured methods, prompt_dir selects the shared method instructions.
Each attempt has its own output directory.

In run_record.json, usage counts tokens from all calls made by this runner,
including the simulated designer. method_usage counts the formulation calls
used for the paper's cost metric, including any repair. Scoring is separate.
For direct LLM use, both totals include all generation calls.
"""
import hashlib
import json
import time
from datetime import datetime, timezone
from itertools import count
from pathlib import Path

from . import contract
from .case import Case, LEVELS


METHODS = ('llm', 'gd_rules', 'axiogd')


def _now():
    return datetime.now(timezone.utc).isoformat()


def _write_json(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def _reserve_output(root, record):
    """Reserve a fresh record without overwriting existing or concurrent runs."""
    root.mkdir(parents=True, exist_ok=True)
    for attempt in count(1):
        folder = root
        if attempt == 1:
            if any(root.iterdir()):
                continue
        else:
            folder = root / f'attempt_{attempt}'
            try:
                folder.mkdir()
            except FileExistsError:
                continue
        record['attempt'] = attempt
        try:
            with (folder / 'run_record.json').open('x', encoding='utf-8') as stream:
                json.dump(record, stream, indent=2)
        except FileExistsError:
            continue
        return folder


class SingleTurnInputError(ValueError):
    """An inconsistency in the initial direct LLM prompt and case."""


def _single_turn_messages(case, level, prompt_dir):
    view = case.agent_view(level)
    request = view['request']
    ordered = request[:1] + view['existing_part'] + request[1:]
    preamble = '\n\n'.join(item['text'] for item in ordered) + '\n\n'
    if prompt_dir is None:
        question = case.meta.get('llm_study_question')
        if not isinstance(question, str) or not question.strip():
            raise SingleTurnInputError('Supply prompt_dir or the case metadata field llm_study_question.')
        system = 'You are a helpful assistant.'
        user = preamble + question
    else:
        root = Path(prompt_dir)
        settings_file = root.parent / 'settings.json'
        settings = json.loads(settings_file.read_bytes()) if settings_file.is_file() else {}
        if settings.get('case_id', case.case_id) != case.case_id or settings.get('level', level) != level:
            raise SingleTurnInputError('The selected messages belong to a different case or request version.')

        message_file = root / 'initial_messages.json'
        if message_file.is_file():
            messages = json.loads(message_file.read_bytes())
            if (not isinstance(messages, list) or len(messages) != 2
                    or any(not isinstance(m, dict) for m in messages)
                    or [m.get('role') for m in messages] != ['system', 'user']):
                raise SingleTurnInputError('Expected one system message followed by one user message.')
            system, user = (m.get('content') for m in messages)
            if any(root.glob('request_*.txt')):
                version_file = root / f'request_{level}.txt'
                if not version_file.is_file() or not isinstance(user, str):
                    raise SingleTurnInputError('The selected request version is unavailable.')
                if version_file.read_bytes().decode('utf-8').strip() != user.strip():
                    raise SingleTurnInputError('The user message does not match the selected request version.')
        else:
            system = (root / 'system.txt').read_bytes().decode('utf-8')
            user = (root / 'user.txt').read_bytes().decode('utf-8')
            if 'case_id' not in settings or 'level' not in settings:
                prefix, separator, question = user.rpartition('\n\n')
                if prefix + separator != preamble or not question.strip():
                    raise SingleTurnInputError('The messages do not match the selected case and request version.')
    if not all(isinstance(value, str) and value.strip() for value in (system, user)):
        raise SingleTurnInputError('Expected nonempty system and user messages.')
    return [{'role': 'system', 'content': system}, {'role': 'user', 'content': user}]


def _direct_llm(case, level, model, key, transport, prompt_dir, folder, record, cancel, answer_questions):
    messages = _single_turn_messages(case, level, prompt_dir)
    record['prompt_hashes'] = {
        m['role']: hashlib.sha256(m['content'].encode('utf-8')).hexdigest() for m in messages
    }
    if transport is None:
        from .llm import call_openai
        transport = call_openai

    for stage in ('first_reply', 'final_reply'):
        request = {'model': model, 'store': False, 'reasoning': {'effort': 'medium'},
                   'max_output_tokens': 32000, 'input': messages}
        prepare = getattr(transport, 'prepare', None)
        if prepare is not None:
            request = prepare(request)
        if cancel is not None and cancel.is_set():
            record['status'] = 'cancelled'
            return
        call = {'stage': stage, 'status': 'requesting'}
        record['calls'].append(call)
        record['usage'] = record['method_usage'] = None
        _write_json(folder / 'run_record.json', record)
        response = transport(request, key)
        parts = []
        for item in response.get('output', []):
            if item.get('type') == 'message':
                for part in item.get('content', []):
                    if part.get('type') == 'output_text':
                        parts.append(part.get('text', ''))
                    elif part.get('type') == 'refusal':
                        parts.append(part.get('refusal', ''))
        raw = ''.join(parts)
        filename = f'{stage}_raw.txt'
        if raw:
            temp = folder / f'{stage}_raw.tmp'
            temp.write_bytes(raw.encode('utf-8'))
            temp.replace(folder / filename)

        usage = response.get('usage') or {}
        call['usage'] = {k: usage.get(k) for k in ('input_tokens', 'output_tokens', 'total_tokens')}
        totals = {}
        for field in call['usage']:
            values = [c['usage'][field] for c in record['calls']]
            totals[field] = sum(values) if all(isinstance(v, int) for v in values) else None
        record['usage'] = totals
        record['method_usage'] = dict(totals)
        if response.get('status') != 'completed' or not raw.strip():
            call['status'] = record['status'] = 'incomplete'
            return
        call['status'] = 'completed'
        if stage == 'first_reply' and answer_questions is not None:
            _write_json(folder / 'run_record.json', record)
            if cancel is not None and cancel.is_set():
                record['status'] = 'cancelled'
                return
            reply = answer_questions(raw)
            if cancel is not None and cancel.is_set():
                record['status'] = 'cancelled'
                return
            if reply is not None and not isinstance(reply, str):
                raise TypeError('answer_questions must return reply text or None.')
            if reply and reply.strip():
                (folder / 'designer_reply.txt').write_bytes(reply.encode('utf-8'))
                messages = messages + [{'role': 'assistant', 'content': raw},
                                       {'role': 'user', 'content': reply}]
                continue
        record['final_reply_file'] = filename
        record['status'] = 'completed'
        return


def _structured(case, level, method, model, key, transport, prompt_dir, folder, record, cancel):
    from .methods import run_axiogd, run_baseline
    from . import prompts
    from .llm import Session, call_openai, sum_usage

    p = prompts.load(prompt_dir) if prompt_dir is not None else prompts.load()
    trace = {}
    record['contract_version'] = contract.VERSION
    record['prompt_hashes'] = {name: hashlib.sha256(value.encode('utf-8')).hexdigest()
                               for name, value in p.items()}

    def save_progress():
        # Transport errors and raw payloads may contain machine-specific paths.
        record['calls'] = [{k: call.get(k) for k in ('stage', 'status', 'elapsed_seconds', 'usage')}
                           for call in session.calls]
        record['usage'] = sum_usage(session.calls)
        record['method_usage'] = sum_usage(
            call for call in session.calls if call['stage'] != 'DESIGNER-MATCH'
        )
        _write_json(folder / 'run_record.json', record)

    session = Session(model, key, transport or call_openai, on_change=save_progress, cancel=cancel)
    view = case.agent_view(level)
    base_ids = case.input_ids(level)
    ad_ids = None
    try:
        if method == 'axiogd':
            final, answers, ad_ids = run_axiogd(session, p, view, case.facts, base_ids, trace)
        else:
            final, answers = run_baseline(session, p, view, case.facts, 'gd_rules', base_ids, trace)

        input_ids = base_ids | {a['id'] for a in answers}
        final, changed = contract.normalize_refs(final)
        issues = contract.validate(final, input_ids, ad_ids)
        trace['first_violations'] = issues
        if issues:
            record['repair_count'] = 1
            context = dict(trace['repair_context'], current_formulation=final,
                           violations=contract.format_violations(issues))
            patch = session.ask('PATCH-REPAIR', prompts.repair_developer(p), context,
                                'gd_patch_v1', contract.PATCH_SCHEMA)
            final, more = contract.normalize_refs(contract.merge_patch(final, patch))
            changed += more
            issues = contract.validate(final, input_ids, ad_ids)
        trace['final_violations'] = issues
        record['ref_normalizations'] = changed
        record['violation_count'] = len(issues)
        record['readiness'] = contract.readiness(final)
        _write_json(folder / 'final_formulation.json', final)
        record['status'] = 'validation_failed' if issues else 'completed'
    finally:
        # Keep the intermediate outputs and clarification history once.
        trace.pop('repair_context', None)
        if trace:
            _write_json(folder / 'method_steps.json', trace)


def run_cell(case_dir, level, method, model, out_dir, key, transport=None, prompt_dir=None,
             cancel=None, *, answer_questions=None):
    """Run one method. For direct LLM use, answer_questions(first_reply) lets
    the designer return a text answer to a clarification request, or None when
    there is nothing to answer. Without a responder the run ends at the first reply.
    """
    if method not in METHODS:
        raise ValueError(f'method must be one of {METHODS}')
    if level not in LEVELS:
        raise ValueError(f'level must be one of {LEVELS}')
    start = time.monotonic()
    record = {'case_id': None, 'level': level, 'method': method, 'model': model, 'status': 'running',
              'started_at_utc': _now(), 'repair_count': 0, 'calls': [],
              'usage': None, 'method_usage': None}
    folder = _reserve_output(Path(out_dir), record)
    try:
        case = Case(case_dir)
        record['case_id'] = case.case_id
        if method == 'llm':
            _direct_llm(case, level, model, key, transport, prompt_dir, folder, record, cancel, answer_questions)
        else:
            _structured(case, level, method, model, key, transport, prompt_dir, folder, record, cancel)
    except KeyboardInterrupt:
        record['status'] = 'interrupted'
        raise
    except Exception as exc:
        record['status'] = 'stopped'
        # Exception messages and tracebacks may expose credentials or absolute paths.
        record['error_type'] = type(exc).__name__
        if isinstance(exc, SingleTurnInputError):
            record['error'] = str(exc)
        elif isinstance(exc, ModuleNotFoundError):
            record['missing_module'] = exc.name
        elif isinstance(exc, FileNotFoundError) and exc.filename:
            record['missing_file'] = Path(exc.filename).name
    finally:
        if record['calls'] and record['calls'][-1]['status'] == 'requesting':
            record['calls'][-1]['status'] = record['status']
        record['call_count'] = len(record['calls'])
        record['finished_at_utc'] = _now()
        record['wall_time_seconds'] = round(time.monotonic() - start, 3)
        _write_json(folder / 'run_record.json', record)
    return record
