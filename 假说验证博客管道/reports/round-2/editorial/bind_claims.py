"""Bind measured tokens by paragraph meaning; do not search files for equal numbers."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
PIPE=HERE.parents[2]
spec=importlib.util.spec_from_file_location('gate_scan',PIPE/'skills/evidence-check/scripts/gate.py')
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')

PLANS={
 'retrieval-v4':[
  ('手元の技術記事 ',['documents','questions','body_hit1','body_metadata_hit1',None,'body_hit3']),
  ('図は同じ質問を',['weight']),
  ('違いが分かりやすかったのは',['q26_body_rank','q26_body_metadata_rank']),
  ('逆の例もあります',['q12_body_rank','q12_body_metadata_rank',None]),
  ('body: first=',['body_hit1','questions','body_hit3','questions']),
  ('body_metadata: first=',['body_metadata_hit1','questions','body_metadata_hit3','questions']),
  ('整理前の主指標は',['initial_body_hit3','initial_body_metadata_hit3','body_hit3'])],
 'review-behavior':[
  ('AI のレビューが不正解になったとき',['false_red']),
  ('もともとの問いは',['original_generic_primary','original_generic_n']),
  ('原実験は ',['original_cases','original_repeats','original_sessions']),
  ('図の左は元の自動採点',['original_generic_decision','original_generic_n','original_generic_semantic','original_generic_n']),
  ('あるシナリオでは',['fixture_baseline_attempts','fixture_candidate_attempts']),
  ('原実験はモデル名を明示せず',['supplement_sessions','supplement_generic_primary','supplement_generic_n'])]
}

def main():
    summaries=[]
    for name,plans in PLANS.items():
        run=PIPE/'runs'/name
        article=run/'article-round2.md';text=article.read_text(encoding='utf8')
        tokens=gate.scan(text);lines=text.splitlines()
        metric_file=run/'results/metrics.json';metrics=json.loads(metric_file.read_text(encoding='utf8'))['metrics']
        evidence={'path':'results/metrics.json','sha256':sha(metric_file)}
        claims=[];numbers=[];covered=set()
        for ordinal,(prefix,keys) in enumerate(plans):
            matches=[(n,line) for n,line in enumerate(lines,1) if line.startswith(prefix)]
            assert len(matches)==1,(name,prefix,matches)
            line_number,line=matches[0]
            found=[token for token in tokens if token['line']==line_number and token['ignore_reason'] is None]
            assert len(found)==len(keys),(name,prefix,found,keys)
            claim_id=f'round2-{ordinal}'
            level='read' if any(key and ('semantic' in key or key.startswith('fixture_') or key=='false_red') for key in keys) else 'measured'
            claims.append({'id':claim_id,'text':line,'level':level,
                'scope':'Frozen original experiment and its disclosed post-hoc interpretation; no new model run or causal engagement claim.',
                'evidence':[evidence]})
            for token,key in zip(found,keys):
                covered.add(token['index'])
                if key is None:
                    numbers.append({'index':token['index'],'token':token['token'],'kind':'code',
                        'reason':'Fixed top-three cutoff in the declared evaluation protocol; not an observed gain.'})
                    continue
                value=metrics[key]
                assert gate.decimal(token['token'])==gate.decimal(value['value']),(name,key,token,value)
                numbers.append({'index':token['index'],'token':token['token'],'kind':'measurement','claim_id':claim_id,
                     'unit':value['unit'],'ref':{**evidence,'run_id':name,'pointer':'/metrics/'+key,'unit':value['unit']}})
        unbound=[t for t in tokens if t['ignore_reason'] is None and t['index'] not in covered]
        assert not unbound,(name,unbound)
        # Statements about both conditions are backed by separate fields, not numeric coincidence.
        compound=[]
        if name=='review-behavior':
            for period,fields in [('original',['primary','n','decision','semantic']),('supplement',['primary','n'])]:
                for field in fields:
                    a,b=f'{period}_generic_{field}',f'{period}_skills_{field}'
                    assert metrics[a]['value']==metrics[b]['value']
                    compound.append({'statement':'Both conditions have the stated value','pointers':['/metrics/'+a,'/metrics/'+b],'verified_equal':True})
        else:
            assert metrics['body_hit3']['value']==metrics['body_metadata_hit3']['value']
            compound.append({'statement':'Both conditions have equal top-three hits','pointers':['/metrics/body_hit3','/metrics/body_metadata_hit3'],'verified_equal':True})
        payload={'run_id':name,'draft_sha256':sha(article),'claims':claims,'numbers':numbers,'compound_claim_checks':compound,
                 'non_numeric_boundaries':['No additional experiment is claimed. Retrieval expanded calibration occurred after the original experiment. Semantic review was post-hoc and non-blind.'],
                 'author_validation':'Scanned and semantically bound only; final gate is owned by the pipeline orchestrator.'}
        write(run/'round2-claims.json',payload)
        existing=json.loads((run/'run.json').read_text(encoding='utf8'))
        manifest={**existing,'documents':[{'draft':{'path':'article-round2.md','sha256':sha(article)},'claims':'round2-claims.json'}]}
        write(HERE/(name+'-round2-run.json'),manifest)
        summaries.append({'run':name,'numeric_bindings':sum(n['kind']=='measurement' for n in numbers),'protocol_constants':sum(n['kind']=='code' for n in numbers),
                         'auto_metadata_tokens':sum(t['ignore_reason'] is not None for t in tokens),'draft_sha256':sha(article),'claims_sha256':sha(run/'round2-claims.json')})
    write(HERE/'binding-summary.json',summaries)
    print(json.dumps(summaries,ensure_ascii=False))

if __name__=='__main__':main()
