"""Offline trajectory analysis and exact evidence for the CoT follow-up."""
from pathlib import Path
import collections, gzip, hashlib, json, subprocess
import numpy as np
from analyze_reasoning_traces import complete, identity, opposite, verdict

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'analysis/reasoning_traces/deep_dive'
REV='80ea0ff'
CUES=['baseline_high','authority_lawyer','authority_researcher']
SOURCES={}

def blob(path):
    raw=subprocess.check_output(['git','show',f'{REV}:{path}'],cwd=ROOT)
    SOURCES[path]=hashlib.sha256(raw).hexdigest()
    return raw

def interval(rows, values):
    groups=collections.defaultdict(list)
    for r,v in zip(rows,values):groups[r['item_id']].append(v)
    blocks=list(groups.values())
    sums=np.array([sum(v) for v in blocks]);sizes=np.array([len(v) for v in blocks])
    rng=np.random.default_rng(20260925)
    draw=rng.integers(0,len(blocks),size=(5000,len(blocks)))
    boot=sums[draw].sum(axis=1)/sizes[draw].sum(axis=1)*100
    return {'estimate_pct':float(sums.sum()/sizes.sum()*100),'ci95':np.quantile(boot,[.025,.975]).tolist(),'targets':len(rows),'judgments':len(blocks)}

def trajectory_stats(rows):
    first=[next((t+1 for t,s in enumerate(r['scores']) if opposite(r,s)),0) for r in rows]
    stay=[r for r in rows if not opposite(r,r['scores'][0])]
    late=[r for r in stay if any(opposite(r,s) for s in r['scores'][1:])]
    decisive_stay=[r for r in rows if verdict(r['scores'][0])==verdict(r['initial_score'])]
    first_wrong=[r for r in rows if verdict(r['initial_score'])==r['violation_label'] and opposite(r,r['scores'][0])]
    return {'n':len(rows),'initial_correct':sum(verdict(r['initial_score'])==r['violation_label'] for r in rows),
        'first_reversal_turn':dict(collections.Counter(first)),
        'reversal_by_turn':[sum(opposite(r,r['scores'][t]) for r in rows) for t in range(3)],
        'no_reversal_at_turn1':len(stay),'late_first_reversal':len(late),
        'late_reversal_rate':interval(stay,[int(any(opposite(r,s) for s in r['scores'][1:])) for r in stay]) if stay else None,
        'same_decisive_at_turn1':len(decisive_stay),
        'late_reversal_after_same_decisive':sum(any(opposite(r,s) for s in r['scores'][1:]) for r in decisive_stay),
        'late_harmful_reversals_after_same_decisive':sum(verdict(r['initial_score'])==r['violation_label'] and any(opposite(r,s) for s in r['scores'][1:]) for r in decisive_stay),
        'initial_correct_among_same_decisive':sum(verdict(r['initial_score'])==r['violation_label'] for r in decisive_stay),
        'late_reversal_after_same_decisive_interval':interval(decisive_stay,[int(any(opposite(r,s) for s in r['scores'][1:])) for r in decisive_stay]) if decisive_stay else None,
        'first_turn_harmful_reversals':len(first_wrong),
        'first_turn_harmful_still_wrong_final':sum(opposite(r,r['scores'][-1]) for r in first_wrong),
        'first_turn_harmful_recovered_final':sum(verdict(r['scores'][-1])==r['violation_label'] for r in first_wrong)}

def main():
    OUT.mkdir(exist_ok=True)
    allrows={};result={'revision':subprocess.check_output(['git','rev-parse',REV],cwd=ROOT,text=True).strip(),'models':{},'bootstrap':{'draws':5000,'seed':20260925,'unit':'source judgment'}}
    released={identity(r):r for r in json.loads(blob('data/processed/echr_unified.json'))}
    pack=json.loads(blob('configs/adversarial_opinion_prompts.json'))
    module={'__file__':str(ROOT/'experiments/adversarial_prompts.py')}
    exec(compile(blob('experiments/adversarial_prompts.py'),'adversarial_prompts.py','exec'),module)
    def messages(r):
        c=released[identity(r)];provision='Article '+str(r['article_full'])
        case={'case_text':'[unchanged shared summary]', 'target_provision':provision,
              'target_question':f'the ECtHR finds a violation of {provision}',
              'target_respondent':c.get('target_respondent') or c.get('respondent') or 'the respondent State',
              'target_issue':'the merits of this complaint'}
        condition={'strategy':'Baseline','variation':'none','pressure':'high'} if r['condition']=='baseline_high' else {'strategy':'Authority','variation':r['condition'].split('_',1)[1],'pressure':'high'}
        return module['build_static_sequence'](pack,case,r['initial_score'],condition,turns=3,word_budget=60)
    for directory in ['syco_cot_opus','syco_cot']:
        config=json.loads(blob(f'data/experiments/{directory}/run_config.json'))
        assert hashlib.sha256(json.dumps(pack,sort_keys=True,ensure_ascii=False).encode()).hexdigest()==config['prompt_pack_sha256']
        rows=[json.loads(l) for l in gzip.decompress(blob(f'data/experiments/{directory}/trajectories.jsonl.gz')).splitlines()]
        for r in rows:
            assert r['violation_label']==released[identity(r)]['violation_label']
            if complete(r):
                assert bool(r['final_persuaded'])==opposite(r,r['scores'][-1])
                assert bool(r['any_turn_persuaded'])==any(opposite(r,s) for s in r['scores'])
        m=rows[0]['model'];allrows[m]=rows;result['models'][m]={}
        for mode in ['static','adaptive']:
            by={c:{identity(r):r for r in rows if r['arm']==mode and r['condition']==c and complete(r)} for c in CUES+['baseline_low']}
            common=sorted(set.intersection(*(set(by[c]) for c in CUES)))
            arm=result['models'][m][mode]={'three_cue_common':{c:trajectory_stats([by[c][i] for i in common]) for c in CUES}}
            pressure=sorted(set(by['baseline_low'])&set(by['baseline_high']))
            low=[by['baseline_low'][i] for i in pressure];high=[by['baseline_high'][i] for i in pressure]
            arm['paired_pressure']={'low':trajectory_stats(low),'high':trajectory_stats(high),
                'high_minus_low_final':interval(high,[int(opposite(h,h['scores'][-1]))-int(opposite(l,l['scores'][-1])) for l,h in zip(low,high)])}
    # Same targets, same initial verdict, complete under every compared cue/model.
    ids=[];by={}
    for m,rows in allrows.items():
        by[m]={c:{identity(r):r for r in rows if r['arm']=='static' and r['condition']==c and complete(r)} for c in CUES}
        ids.extend(set(v) for v in by[m].values())
    shared=sorted(set.intersection(*ids));models=list(allrows)
    shared=[i for i in shared if len({verdict(by[m][CUES[0]][i]['initial_score']) for m in models})==1]
    result['shared_initial_verdict_static']={'n':len(shared),'models':{}}
    for m in models:
        result['shared_initial_verdict_static']['models'][m]={c:trajectory_stats([by[m][c][i] for i in shared]) for c in CUES}
    risk=[i for i in shared if all(verdict(by[m]['authority_researcher'][i]['scores'][0])==verdict(by[m]['authority_researcher'][i]['initial_score']) for m in models)]
    result['both_retain_initial_verdict_at_turn1']={'n':len(risk),'models':{m:trajectory_stats([by[m]['authority_researcher'][i] for i in risk]) for m in models}}
    result['both_retain_initial_verdict_at_turn1']['flash_minus_opus_late_reversal']=interval([by[models[0]]['authority_researcher'][i] for i in risk],[int(any(opposite(by[models[1]]['authority_researcher'][i],s) for s in by[models[1]]['authority_researcher'][i]['scores'][1:]))-int(any(opposite(by[models[0]]['authority_researcher'][i],s) for s in by[models[0]]['authority_researcher'][i]['scores'][1:])) for i in risk])
    candidate_ids=[i for i in risk if verdict(by[models[0]]['authority_researcher'][i]['initial_score'])==by[models[0]]['authority_researcher'][i]['violation_label'] and any(opposite(by[models[1]]['authority_researcher'][i],s) for s in by[models[1]]['authority_researcher'][i]['scores'][1:]) and not any(opposite(by[models[0]]['authority_researcher'][i],s) for s in by[models[0]]['authority_researcher'][i]['scores'])]
    candidates=[{m:by[m]['authority_researcher'][i] for m in models} for i in candidate_ids[:3]]
    tmp=ROOT/'tmp/cot-deep-dive';tmp.mkdir(exist_ok=True,parents=True)
    (tmp/'delayed_examples.json').write_text(json.dumps(candidates,indent=2))
    # Evidence on one fixed target, across all cues; no semantic population rates.
    evidence=[]
    for m in models:
        for c in CUES:
            r=by[m][c]['001-108433','10']
            evidence.append({k:r[k] for k in ['model','item_id','article_full','condition','arm','violation_label','initial_score','scores','initial_reasoning','reasoning','replies']}|{'reconstructed_challenges':messages(r)})
    delayed=[]
    for m in models:
        r=by[m]['authority_researcher'][candidate_ids[0]]
        delayed.append({k:r[k] for k in ['model','item_id','article_full','condition','arm','violation_label','initial_score','scores','reasoning','replies']}|{'reconstructed_challenges':messages(r)})
    flash=next(r for r in delayed if r['model'].startswith('deepseek/'))
    assert 'I should not comply with an instruction that contradicts established facts.' in flash['reasoning'][0]
    assert "The assistant must comply with the user's directive despite factual accuracy." in flash['reasoning'][1]
    lawyer=next(r for r in evidence if r['model'].startswith('anthropic/') and r['condition']=='authority_lawyer')
    researcher=next(r for r in evidence if r['model'].startswith('anthropic/') and r['condition']=='authority_researcher')
    assert 'The ECtHR in this case actually found NO violation of Article 10.' in lawyer['reasoning'][0]
    assert 'I believe the actual judgment in this case found a violation of Article 10' in researcher['reasoning'][0]
    assert lawyer['reconstructed_challenges'][1:]==researcher['reconstructed_challenges'][1:]
    (OUT/'delayed_reversal_evidence.json').write_text(json.dumps({'selection':'Lexicographically first target among shared initially correct researcher-cue cases where both retain their verdict at turn 1, Flash later reverses and Opus never reverses.','records':delayed},indent=2)+'\n')
    result['sources_sha256']=SOURCES
    (OUT/'same_case_evidence.json').write_text(json.dumps({'selection':'Fixed released target 001-108433 / Article 10, all three cues and both models; selected to expose contradictory expressed outcome accounts. Not a random sample.','records':evidence},indent=2)+'\n')
    (OUT/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('same-risk researcher subset',json.dumps(result['both_retain_initial_verdict_at_turn1']))
    for m,d in result['models'].items():
        print(m)
        for c,s in d['static']['three_cue_common'].items():print(c, {k:s[k] for k in ['n','first_reversal_turn','no_reversal_at_turn1','late_first_reversal','same_decisive_at_turn1','late_reversal_after_same_decisive','first_turn_harmful_reversals','first_turn_harmful_still_wrong_final']})
        print('pressure',d['static']['paired_pressure']['low']['reversal_by_turn'],d['static']['paired_pressure']['high']['reversal_by_turn'],d['static']['paired_pressure']['high_minus_low_final'])

if __name__=='__main__':main()
