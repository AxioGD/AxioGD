"""Validate the JSON Schema subset used for strict structured outputs."""

STR = {'type': 'string'}
STRS = {'type': 'array', 'items': {'type': 'string'}}


def obj(props):
    """A strict object: every property required, no extra properties."""
    return {'type': 'object', 'properties': props, 'required': list(props),
            'additionalProperties': False}


_TYPES = {
    'object': lambda v: isinstance(v, dict),
    'array': lambda v: isinstance(v, list),
    'string': lambda v: isinstance(v, str),
    'null': lambda v: v is None,
    'boolean': lambda v: isinstance(v, bool),
    'integer': lambda v: isinstance(v, int) and not isinstance(v, bool),
    'number': lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
}


def validate(value, schema, path='$'):
    kinds = schema.get('type', [])
    kinds = [kinds] if isinstance(kinds, str) else list(kinds)
    if kinds and not any(_TYPES[k](value) for k in kinds):
        return [f'{path}: expected {"/".join(kinds)}']
    if 'enum' in schema and value not in schema['enum']:
        return [f'{path}: {value!r} is not one of {schema["enum"]}']
    issues = []
    if isinstance(value, dict):
        props = schema.get('properties', {})
        for name in schema.get('required', []):
            if name not in value:
                issues.append(f'{path}: missing field {name}')
        if schema.get('additionalProperties') is False:
            issues.extend(f'{path}: unexpected field {name}' for name in value if name not in props)
        for name, item in value.items():
            if name in props:
                issues.extend(validate(item, props[name], f'{path}.{name}'))
    elif isinstance(value, list) and 'items' in schema:
        for index, item in enumerate(value):
            issues.extend(validate(item, schema['items'], f'{path}[{index}]'))
    return issues
