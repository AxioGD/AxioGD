"""OpenAI Responses API calls, request building and per-call records (standard library only)."""
import json
import time
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .jsonschema_lite import validate as schema_validate

API_URL = 'https://api.openai.com/v1/responses'
MAX_OUTPUT_TOKENS = 32000
TIMEOUT_SECONDS = 900
RATE_LIMIT_WAITS = (5, 20)


class StageFailure(Exception):
    """A model call failed; the run stops and the record keeps everything so far."""


class RateLimited(Exception):
    """HTTP 429. Structured calls retry after the configured waits."""


class _APIRequestError(RuntimeError):
    """A diagnostic generated locally, safe to include in a stage failure."""


def now():
    return datetime.now(timezone.utc).isoformat()


def build_request(model, developer, user_obj, schema_name, schema, effort,
                  max_output_tokens=MAX_OUTPUT_TOKENS):
    return {'model': model, 'store': False, 'reasoning': {'effort': effort},
            'max_output_tokens': max_output_tokens,
            'input': [{'role': 'developer', 'content': developer},
                      {'role': 'user', 'content': json.dumps(user_obj, ensure_ascii=False)}],
            'text': {'format': {'type': 'json_schema', 'name': schema_name, 'strict': True,
                                'schema': schema}}}


def call_openai(request, key):
    try:
        req = Request(API_URL, data=json.dumps(request).encode('utf-8'), method='POST',
                      headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json'})
        with urlopen(req, timeout=TIMEOUT_SECONDS) as response:
            return json.load(response)
    except HTTPError as exc:
        exc.close()
        if exc.code == 429:
            raise RateLimited('API HTTP 429 (rate limit)') from None
        raise _APIRequestError(f'API HTTP {exc.code}') from None
    except URLError:
        raise _APIRequestError('API connection failed') from None
    except Exception as exc:
        # Transport and decoding errors can include headers or response text.
        raise _APIRequestError(f'API request failed ({type(exc).__name__})') from None


def answer_text(response):
    return ''.join(part.get('text', '') for item in response.get('output', [])
                   if item.get('type') == 'message'
                   for part in item.get('content', []) if part.get('type') == 'output_text')


def usage_of(response):
    u = (response or {}).get('usage') or {}
    return {'input_tokens': u.get('input_tokens'), 'output_tokens': u.get('output_tokens'),
            'reasoning_tokens': (u.get('output_tokens_details') or {}).get('reasoning_tokens'),
            'cached_tokens': (u.get('input_tokens_details') or {}).get('cached_tokens'),
            'total_tokens': u.get('total_tokens')}


ZERO_USAGE = {'input_tokens': 0, 'output_tokens': 0, 'reasoning_tokens': 0, 'cached_tokens': 0, 'total_tokens': 0}


def sum_usage(calls):
    """Known token sums over the calls, plus how many calls have unknown usage (failed before a response)."""
    totals = {key: 0 for key in ('input_tokens', 'output_tokens', 'reasoning_tokens', 'total_tokens')}
    unknown = 0
    for c in calls:
        usage = c.get('usage') or {}
        if not isinstance(usage.get('total_tokens'), int):
            unknown += 1
            continue
        for key in totals:
            value = usage.get(key)
            if isinstance(value, int) and not isinstance(value, bool):
                totals[key] += value
    totals['unknown_calls'] = unknown
    return totals


class Session:
    """All model calls of one cell; each request and response is appended to `calls`."""

    def __init__(self, model, key, transport=call_openai, on_change=None, sleep=time.sleep, cancel=None):
        self.model, self.key, self.transport = model, key, transport
        self.on_change, self.sleep, self.cancel = on_change, sleep, cancel
        self.calls = []

    def ask(self, stage, developer, user_obj, schema_name, schema, effort='medium'):
        request = build_request(self.model, developer, user_obj, schema_name, schema, effort)
        prepare = getattr(self.transport, 'prepare', None)
        if prepare:  # Record the request after transport preparation.
            try:
                request = prepare(request)
            except Exception as exc:
                raise StageFailure(f'{stage}: request preparation failed ({type(exc).__name__})') from None
        entry = {'stage': stage, 'request': request, 'started_at_utc': now(), 'status': 'requesting',
                 'rate_limit_retries': 0, 'elapsed_seconds': None, 'raw_response': None,
                 'usage': None, 'answer': None, 'issues': []}
        self.calls.append(entry)
        if self.cancel is not None and self.cancel.is_set():
            entry.update(status='cancelled', usage=dict(ZERO_USAGE), elapsed_seconds=0.0, finished_at_utc=now())
            self._changed()
            raise StageFailure(f'{stage}: cancelled before sending')
        self._changed()
        tick = time.monotonic()
        try:
            response = self._send(request, entry)
            entry['raw_response'] = response
            entry['usage'] = usage_of(response)
            entry['returned_settings'] = {k: response.get(k) for k in
                                          ('model', 'reasoning', 'temperature', 'top_p',
                                           'max_output_tokens', 'service_tier')}
            if response.get('status') != 'completed':
                entry['status'] = 'api_incomplete'
                raise StageFailure(f'{stage}: API response did not complete')
            try:
                value = json.loads(answer_text(response))
            except ValueError:
                entry['status'] = 'invalid_json'
                raise StageFailure(f'{stage}: the response is not valid JSON') from None
            entry['answer'] = value
            entry['issues'] = schema_validate(value, schema)
            if entry['issues']:
                entry['status'] = 'invalid_structure'
                raise StageFailure(f'{stage}: response failed schema validation ({len(entry["issues"])} issues)')
            entry['status'] = 'completed'
            return value
        finally:
            entry['elapsed_seconds'] = round(time.monotonic() - tick, 3)
            entry['finished_at_utc'] = now()
            self._changed()

    def _send(self, request, entry):
        attempts = len(RATE_LIMIT_WAITS) + 1
        for attempt in range(attempts):
            try:
                return self.transport(request, self.key)
            except RateLimited:
                if attempt == attempts - 1:
                    entry['status'] = 'api_failed'
                    raise StageFailure(f"{entry['stage']}: HTTP 429 (rate limit) after {attempts} attempts") from None
                entry['rate_limit_retries'] += 1
                self.sleep(RATE_LIMIT_WAITS[attempt])
            except _APIRequestError as exc:
                entry['status'] = 'api_failed'
                raise StageFailure(f"{entry['stage']}: {exc}") from None
            except HTTPError as exc:
                # An injected transport may raise urllib errors directly.
                entry['status'] = 'api_failed'
                exc.close()
                raise StageFailure(f"{entry['stage']}: API HTTP {exc.code}") from None
            except Exception as exc:
                entry['status'] = 'api_failed'
                raise StageFailure(f"{entry['stage']}: transport failed ({type(exc).__name__})") from None

    def _changed(self):
        if self.on_change:
            self.on_change()
