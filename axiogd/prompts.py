"""Load the text instructions for LLM + GD rules and AxioGD.

Composite stages join prompt fragments in experiment order with a blank line.
"""
import re
from pathlib import Path

PROMPT_DIR = Path(__file__).resolve().parent.parent / 'prompts'
NAMES = (
    'role_llm', 'gd_rules', 'contract_core', 'contract_r1', 'contract_final',
    'ad_req_gd', 'ad_req_update_gd', 'ad_decomp_gd', 'ad_check_gd', 'ad_to_gd',
    'designer_matcher', 'patch_repair',
)


def load(prompt_dir=PROMPT_DIR):
    """Read the published Markdown prompts or a directory of individual text files."""
    root = Path(prompt_dir)
    if (root / 'role_llm.txt').is_file():
        return {name: (root / f'{name}.txt').read_text(encoding='utf-8').strip()
                for name in NAMES}

    text = (root / 'README.md').read_text(encoding='utf-8')
    blocks = re.findall(r'^#### [^\n]*`(\w+)`\n\n```text\n(.*?)\n```$', text, flags=re.M | re.S)
    prompts = {name: content.strip() for name, content in blocks}
    if len(blocks) != len(prompts) or set(prompts) != set(NAMES):
        raise ValueError('Expected one instruction block per prompt in README.md.')
    return {name: prompts[name] for name in NAMES}


def baseline_developer(p, condition, round_name):
    """Assemble the instructions for the first or final round of LLM + GD rules."""
    if condition != 'gd_rules':
        raise ValueError("baseline_developer requires the 'gd_rules' method")
    if round_name not in ('r1', 'final'):
        raise ValueError("round_name must be 'r1' or 'final'")
    round_prompt = p['contract_r1'] if round_name == 'r1' else p['contract_final']
    return '\n\n'.join([p['role_llm'], p['gd_rules'], p['contract_core'], round_prompt])


def ad_req_developer(p):
    return '\n\n'.join([p['ad_req_gd'], p['gd_rules']])


def ad_req_update_developer(p):
    return p['ad_req_update_gd']


def ad_to_gd_developer(p):
    return '\n\n'.join([p['ad_to_gd'], p['gd_rules'], p['contract_core'], p['contract_final']])


def repair_developer(p):
    return '\n\n'.join([p['patch_repair'], p['contract_core']])
