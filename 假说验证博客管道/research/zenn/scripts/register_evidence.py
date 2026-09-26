"""Register semantic report claims. Explicit index/metric bindings, never value search."""
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
from collect import ROOT, write

RUN='zenn-research-20260925'
RULER='zenn-descriptive-features-v1'
GATE=ROOT.parents[1]/'skills/evidence-check/scripts/gate.py'
spec=importlib.util.spec_from_file_location('pipeline_gate',GATE)
gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def ref(path):return {'path':path,'sha256':sha(ROOT/path)}
def read(path):return json.loads((ROOT/path).read_text(encoding='utf8'))

def compute():
    subprocess.run([sys.executable,str(ROOT/'scripts/analyze.py'),'analyze'],check=True)
    subprocess.run([sys.executable,str(ROOT/'scripts/validate.py'),'--live'],check=True)
    # Refresh validation can update an index; take the final measurement afterward.
    subprocess.run([sys.executable,str(ROOT/'scripts/analyze.py'),'analyze'],check=True)
    for name in ['statistics.json','metadata.json','body-features.json','coverage.json','pairs.json','selection.json','detail-index.json','probe.json','probe-extra.json','sampling-plan.json','sitemap-coverage.json','ruler_check.json']:
        shutil.copyfile(ROOT/name,ROOT/'results'/name)
    shutil.copytree(ROOT/'raw',ROOT/'results/raw',dirs_exist_ok=True)
    shutil.copytree(ROOT/'indexes',ROOT/'results/indexes',dirs_exist_ok=True)
    shutil.copytree(ROOT/'scripts',ROOT/'results/analysis-scripts',ignore=shutil.ignore_patterns('__pycache__'),dirs_exist_ok=True)
    stats=read('statistics.json');cov=read('coverage.json');pairs=read('pairs.json');selection=read('selection.json')
    metrics={}
    def put(key,value,unit,source,method):metrics[key]={'value':value,'unit':unit,'source':source,'method':method}
    put('latest_per_topic',600,'articles','results/coverage.json#/coverage','All six latest queries observed 600 unique IDs each; assert below.')
    assert all(x['unique_seen_this_run']==600 for x in cov['coverage'] if x['query']['order']=='latest')
    put('alltime_per_topic',100,'articles','results/coverage.json#/coverage','Six topic alltime query counts.')
    put('global_alltime',200,'articles','results/coverage.json#/coverage','Global alltime query unique count.')
    put('membership_count',sum(x['unique_seen_this_run'] for x in cov['coverage']),'memberships','results/coverage.json#/coverage','Sum unique_seen_this_run across declared queries, before cross-query deduplication.')
    put('unique_articles',stats['unique_articles'],'articles','results/statistics.json#/unique_articles','Deduplicate list article IDs across query indexes.')
    put('maturity_days',7,'days','results/analysis-scripts/analyze.py','Predefined age inclusion threshold, not measured improvement.')
    put('mature_articles',stats['recent_mature_unique'],'articles','results/statistics.json#/recent_mature_unique','Unique latest IDs with age_days >= 7 at snapshot time.')
    put('detail_articles',len(selection),'articles','results/selection.json','Length of declared selected detail IDs.')
    put('pair_count',len(pairs),'pairs','results/pairs.json','Number of topic/month matched high-low pairs.')
    put('match_window_days',14,'days','results/analysis-scripts/analyze.py','Predeclared maximum absolute date difference; all actual gaps within bound.')
    put('historical_articles',sum(x['group']=='historical_example' for x in selection),'articles','results/selection.json','Count group == historical_example.')
    sitemap=read('sitemap-coverage.json')['total_listed_urls']
    put('sitemap_urls',sitemap,'urls','results/sitemap-coverage.json#/sitemaps','Sum XML root child URL entry counts over the six fetched article sitemaps.')
    put('assumed_page_size',100,'articles_per_request','results/probe.json','Assumption for extrapolated lower-bound cost, observed working count, not proof of deep pagination.')
    put('estimated_list_requests',math.ceil(sitemap/100),'requests','results/sitemap-coverage.json','ceil(sitemap_urls / observed_page_size). Model estimate, not executed full crawl.')
    delay=read('sampling-plan.json')['minimum_interval_seconds']
    put('request_interval',delay,'seconds','results/sampling-plan.json#/minimum_interval_seconds','Declared request interval.')
    put('estimated_list_minutes',math.ceil(sitemap/100)*delay/60,'minutes','results/sitemap-coverage.json','ceil(sitemap_urls/100)*request_interval/60; ignores response cost.')
    put('estimated_detail_hours',sitemap*delay/3600,'hours','results/sitemap-coverage.json','sitemap_urls*request_interval/3600; ignores response cost.')
    probe=read('probe.json');extra=read('probe-extra.json')
    raw=read(probe[6]['source'])
    for i in range(2):put('sort_like_'+str(i),raw['response']['articles'][i]['liked_count'],'likes',str(Path('results')/probe[6]['source']),f'/response/articles/{i}/liked_count; observed field, not own engagement result.')
    put('unknown_sort_ids',len(extra[0]['ids']),'articles','results/probe-extra.json#/0/ids','Compare exact IDs to trending response; assert equality below.')
    assert extra[0]['ids']==extra[1]['ids']
    put('request_count_100',probe[3]['params']['count'],'requested_articles','results/probe.json#/3/params/count','Requested query parameter.')
    put('response_count_100',probe[3]['count_returned'],'articles','results/probe.json#/3/count_returned','Observed list length.')
    put('request_count_200',extra[3]['params']['count'],'requested_articles','results/probe-extra.json#/3/params/count','Requested query parameter.')
    put('response_count_200',extra[3]['count'],'articles','results/probe-extra.json#/3/count','Observed list length.')
    put('tested_page',probe[4]['params']['page'],'page','results/probe.json#/4/params/page','Observed distinct second-page IDs.')
    for row in stats['title_features']:
        for field in ['n','median_likes']:
            for group in ['yes','no']:
                put(row['feature']+'_'+group+'_'+field,row[group][field],'articles' if field=='n' else 'likes','results/statistics.json#/title_features',f"feature={row['feature']}, group={group}, field={field}")
    q=stats['title_features'][0]['topic_month_cells']
    put('question_cells',len(q),'cells','results/statistics.json#/title_features/0/topic_month_cells','Cells with >=5 items in each feature group.')
    put('question_positive_cells',sum(x['log1p_difference']>0 for x in q),'cells','results/statistics.json#/title_features/0/topic_month_cells','Count log1p_difference > 0.')
    put('question_author_positive_cells',sum(x['equal_author_log1p_difference']>0 for x in q),'cells','results/statistics.json#/title_features/0/topic_month_cells','Count equal_author_log1p_difference > 0; not matched author or causal control.')
    for row in stats['body_features']:
        for group in ['higher','lower']:
            for field in ['n','positive']:
                put(row['feature']+'_'+group+'_'+field,row['groups'][group][field],'articles','results/statistics.json#/body_features',f"feature={row['feature']}, group={group}, field={field}")
    put('most_length_median',stats['length_groups'][0]['median_likes'],'likes','results/statistics.json#/length_groups','First four groups all have median 1; assert below.')
    assert all(x['median_likes']==1 for x in stats['length_groups'][:4])
    put('long_length_threshold',20000,'api_body_letters','results/statistics.json#/length_groups/4/range','Lower bound of final declared body_letters_count bin.')
    put('long_length_median',stats['length_groups'][4]['median_likes'],'likes','results/statistics.json#/length_groups/4/median_likes','Median observed likes among mature latest sample final length bin.')
    cal=read('ruler_check.json')
    independent=next(x for x in cal['checks'] if x['name']=='real_html_independent_parser')
    put('parser_comparisons',len(independent['evidence']),'articles','results/ruler_check.json#/checks','Actual detail articles compared by two HTML parsers.')
    write(ROOT/'results/metrics.json',{'run_id':RUN,'metrics':metrics})
    evidence=ref('results/ruler_check.json')
    structural=next(x for x in cal['checks'] if x['name']=='known_structural_positive_negative')['evidence']
    write(ROOT/'results/calibration.json',{'run_id':RUN,'ruler_id':RULER,'status':'passed' if cal['all_passed'] else 'failed',
          'alignment':'HTML counts and declared query counts measure observable sampled features; not true experiments, content quality, exposure or causal effects.',
          'cases':[{'label':label,'expected':value,'observed':structural[key]['images'],'evidence':evidence} for label,key,value in [('good','positive',1),('bad','negative',0)]]})
    print(json.dumps({'computed_metrics':len(metrics),'calibration_passed':cal['all_passed']}))

def register():
    text=(ROOT/'FINDINGS.md').read_text(encoding='utf8'); tokens=gate.scan(text);lines=text.splitlines()
    source=ref('results/metrics.json');metrics=read('results/metrics.json')['metrics']
    # Report indices bind to declared meanings. Any edited report must be rescanned and reviewed.
    keys=['latest_per_topic','alltime_per_topic','global_alltime','membership_count','unique_articles','maturity_days','mature_articles','detail_articles','pair_count','match_window_days','historical_articles','sitemap_urls','assumed_page_size','estimated_list_requests','request_interval','estimated_list_minutes','estimated_detail_hours','sort_like_0','sort_like_1','unknown_sort_ids','request_count_100','response_count_100','request_count_200','response_count_200','tested_page']
    mapping={i+3:k for i,k in enumerate(keys)}
    index=28
    for feat in ['question','number','trial_or_comparison','failure_or_limit','guide_or_summary','firsthand_build']:
        for suffix in ['yes_n','yes_median_likes','no_median_likes']:
            mapping[index]=feat+'_'+suffix;index+=1
    mapping.update({46:'question_cells',47:'question_positive_cells',49:'question_author_positive_cells',50:'images_higher_n',51:'images_lower_n',52:'images_higher_positive',53:'images_lower_positive',54:'code_blocks_higher_positive',55:'code_blocks_lower_positive',56:'tables_higher_positive',57:'tables_lower_positive',58:'measurement_words_higher_positive',59:'measurement_words_higher_n',60:'measurement_words_lower_positive',61:'measurement_words_lower_n',62:'most_length_median',63:'long_length_threshold',64:'long_length_median',65:'parser_comparisons'})
    claims=[]; by_line={};numbers=[]
    # Explicit semantic paragraph types; suggestions are inferred, not execution evidence.
    measured_lines={13,14,15,16,26,36,37,38,39,40,41,43,49,51,52,53,59,61,63,65,101}
    read_lines={11,24,73,74,75,76,77,78}
    for line_no,line in enumerate(lines,1):
        if not line.strip() or line.startswith('#') or line.startswith('|---') or line.startswith('!['):continue
        level='measured' if line_no in measured_lines else 'read' if line_no in read_lines else 'inferred'
        evidence=[source,ref('results/statistics.json')]
        if level=='read':
            evidence.extend(ref('results/'+x['source']) for x in read('detail-index.json') if x['slug'] in ['953334f11df507','824026c76116e0','7ac8cea14c20e8','claude-code-desktop-app','c67ef2c9dd067e','1a3e5b726498d8'])
            evidence.extend([ref('results/probe.json'),ref('results/probe-extra.json')])
        if line_no==101:evidence.append(ref('results/ruler_check.json'))
        claim={'id':'line-'+str(line_no),'text':line,'level':level,'scope':'2026-09-25 declared Zenn sample; descriptive observation, read article content, or explicitly limited recommendation; no causal or publication effect claim.','evidence':evidence}
        claims.append(claim);by_line[line_no]=claim
    for token in tokens:
        i=token['index'];binding={'index':i,'token':token['token']}
        if i in mapping:
            key=mapping[i]; metric=metrics[key]
            binding.update({'kind':'measurement','claim_id':by_line[token['line']]['id'],'unit':metric['unit'],'ref':{**source,'run_id':RUN,'pointer':'/metrics/'+key,'unit':metric['unit']}})
            if i in (18,19):binding['decimals']=0
        elif i<=2:binding.update({'kind':'date','reason':'Snapshot observation date, not a performance metric.'})
        elif i==48:binding.update({'kind':'code','reason':'Mathematical constant in log(1+likes), not an observed count.'})
        elif i>=66:binding.update({'kind':'identifier','reason':'Digits inside cited source URL/slug; not a quantitative claim.'})
        else:raise ValueError('Unreviewed numeric token '+str(token))
        numbers.append(binding)
    write(ROOT/'claims.json',{'run_id':RUN,'draft_sha256':sha(ROOT/'FINDINGS.md'),'claims':claims,'numbers':numbers})
    write(ROOT/'run.json',{'run_id':RUN,'hypothesis':{'falsification':'If title/body patterns vanish or reverse under topic/time/author sensitivity, do not claim universal higher engagement; no causal claim can be established without exposure/control data.'},'outcome':'inconclusive','ruler_id':RULER,'ruler':ref('results/calibration.json'),'execution':ref('results/execution.json'),'budget':{'status':'within','note':'Declared research sample complete; model API cost zero; public endpoint load bounded by sampling plan.'},'documents':[{'draft':ref('FINDINGS.md'),'claims':'claims.json'}]})
    print(json.dumps({'claims':len(claims),'numeric_tokens':len(numbers)}))

if __name__=='__main__':
    compute() if sys.argv[1]=='compute' else register()
