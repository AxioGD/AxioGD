"""Run the two paper methods that produce a structured GD formulation.

LLM + GD rules updates its first formulation when clarification answers are
available. AxioGD analyses the requirements before mapping them to GD
conditions.
"""
from . import ad, contract, designer, prompts as prompt_lib
from .contract import FINAL_SCHEMA

TASK = 'Prepare the GD problem formulation for this request.'
FINAL_NAME = 'gd_formulation_v1'


def base_user(view):
    return {'task': TASK, 'request': view['request'], 'existing_part': view['existing_part']}


def run_baseline(session, p, view, facts, condition, input_ids, trace):
    """Run LLM + GD rules and update the first formulation if clarification answers are available."""
    if condition != 'gd_rules':
        raise ValueError("run_baseline requires the 'gd_rules' method")
    r1 = session.ask('R1', prompt_lib.baseline_developer(p, condition, 'r1'), base_user(view),
                     FINAL_NAME, FINAL_SCHEMA)
    trace['r1'] = r1
    trace['r1_violations'] = contract.validate(contract.normalize_refs(r1)[0], input_ids)
    answers, log = designer.run_designer(session, p, contract.questions(r1), facts)
    trace['designer'] = log
    trace['repair_context'] = {'request': view['request'], 'existing_part': view['existing_part'],
                               'designer_answers': designer.public_answers(answers)}
    if not answers:
        trace['final_round'] = 'r1'
        return r1, []
    user = dict(base_user(view), designer_answers=designer.public_answers(answers),
                previous_round_output=r1)
    final = session.ask('R2', prompt_lib.baseline_developer(p, condition, 'final'), user,
                        FINAL_NAME, FINAL_SCHEMA)
    trace['final_round'] = 'r2'
    return final, answers


def run_axiogd(session, p, view, facts, input_ids, trace):
    """Run the paper's full AxioGD workflow.

    Update the requirement analysis when clarification answers are available.
    Decompose functional requirements marked as having no direct mapping to a
    GD condition, then review the decomposition. If all map directly, proceed
    to the final formulation.
    If the review identifies blocking issues, revise the decomposition and
    review it once more. Carry unresolved blocking issues into the final GD
    formulation step. Return the formulation, answers and AD record IDs.
    """
    user0 = base_user(view)
    req = session.ask('AD-REQ', prompt_lib.ad_req_developer(p), user0, 'ad_req_gd_v04', ad.AD_REQ_SCHEMA)
    trace['ad_req'] = req
    trace['ad_warnings'] = {'AD-REQ': ad.validate_ad_req(req, input_ids)}
    raw = [{'item_ids': q['item_ids'], 'text': q['text'].strip()} for q in req['questions'] if q['text'].strip()]
    answers, log = designer.run_designer(session, p, raw, facts)
    trace['designer'] = log
    public = designer.public_answers(answers)
    if answers:
        update = session.ask('AD-REQ-UPDATE', prompt_lib.ad_req_update_developer(p),
                             dict(user0, designer_answers=public, ad_representation={'ad_req': req}),
                             'ad_req_update_gd_v04', ad.AD_REQ_UPDATE_SCHEMA)
        trace['ad_req_initial'] = req
        req, merge_warnings = ad.merge_req(req, update)
        trace['ad_req'] = req
        trace['ad_warnings']['AD-REQ-UPDATE'] = merge_warnings + ad.validate_ad_req(
            req, input_ids | {a['id'] for a in answers})
    decompose = [i['item_id'] for i in req['items'] if i['category'] == 'FR' and i['maps_directly'] is False]
    trace['decompose_fr_ids'] = decompose
    trace['early_exit'] = not decompose
    representation, carried, dec = {'ad_req': req}, [], None
    if decompose:
        dec_user = dict(user0, designer_answers=public, ad_representation={'ad_req': req},
                        decompose_fr_ids=decompose)
        dec = session.ask('AD-DECOMP', p['ad_decomp_gd'], dec_user, 'ad_decomp_gd_v04', ad.DECOMP_SCHEMA)
        trace['ad_warnings']['AD-DECOMP'] = ad.validate_decomp(dec, req, decompose)
        chk = session.ask('AD-CHECK', p['ad_check_gd'],
                          dict(user0, designer_answers=public,
                               ad_representation={'ad_req': req, 'ad_decomp': dec}),
                          'ad_check_gd_v04', ad.CHECK_SCHEMA)
        trace['ad_warnings']['AD-CHECK'] = ad.validate_check(chk)
        trace['checks'] = [chk]
        blocking = [i for i in chk['issues'] if i['severity'] == 'blocking']
        if blocking:
            dec = session.ask('AD-DECOMP-REV', p['ad_decomp_gd'],
                              dict(dec_user, prior_decomp=dec, review_issues=blocking),
                              'ad_decomp_gd_v04', ad.DECOMP_SCHEMA)
            trace['ad_warnings']['AD-DECOMP-REV'] = ad.validate_decomp(dec, req, decompose)
            chk2 = session.ask('AD-RECHECK', p['ad_check_gd'],
                               dict(user0, designer_answers=public,
                                    ad_representation={'ad_req': req, 'ad_decomp': dec}, prior_issues=blocking),
                               'ad_check_gd_v04', ad.CHECK_SCHEMA)
            trace['ad_warnings']['AD-RECHECK'] = ad.validate_check(chk2, [i['issue_id'] for i in blocking])
            trace['checks'].append(chk2)
            closed = {c['prior_issue_id'] for c in chk2['closure'] if c['closed']}
            carried = ([i for i in blocking if i['issue_id'] not in closed]
                       + [i for i in chk2['issues'] if i['severity'] == 'blocking'])
        trace['decomp'] = dec
        representation = {'ad_req': req, 'ad_decomp': dec, 'ad_check': trace['checks'][-1]}
    trace['carried_issues'] = carried
    map_user = dict(user0, designer_answers=public,
                    ad_representation=dict(representation, carried_issues=carried))
    trace['repair_context'] = {'request': view['request'], 'existing_part': view['existing_part'],
                               'designer_answers': public, 'ad_representation': map_user['ad_representation']}
    final = session.ask('AD-TO-GD', prompt_lib.ad_to_gd_developer(p), map_user, FINAL_NAME, FINAL_SCHEMA)
    return final, answers, ad.ad_ids(req, dec, trace.get('checks', []))
