"""Calibrate structural extraction and verify live cache/incremental behavior."""
import argparse
import json
import re
from collect import ROOT, Client, collect, write
from analyze import body_features, TITLE_RULES

def main():
    p=argparse.ArgumentParser();p.add_argument('--live',action='store_true');args=p.parse_args()
    checks=[]
    def check(name, passed, evidence):
        checks.append({'name':name,'passed':bool(passed),'evidence':evidence})
    good='<h2>結果</h2><p>課題を検証した結果、改善した。</p><pre><code>x=1</code></pre><img src="x"><table><tr><td>2</td></tr></table>'
    bad='<p>こんにちは。</p><p>設定を説明します。</p>'
    a,b=body_features(good),body_features(bad)
    check('known_structural_positive_negative',a['code_blocks']==1 and b['code_blocks']==0 and a['images']==1 and b['images']==0 and a['tables']==1 and b['tables']==0,{'positive':a,'negative':b})
    check('known_opening_problem_positive_negative',a['opening_problem_words'] and not b['opening_problem_words'],{'positive':a['opening'],'negative':b['opening']})
    check('title_trial_positive_negative',bool(re.search(TITLE_RULES['trial_or_comparison'],'RAGを比較検証した')) and not re.search(TITLE_RULES['trial_or_comparison'],'RAGの概要'),{})
    # Explicit counterexample: word presence cannot prove a real experiment.
    misleading=body_features('<p>検証はしていません。</p>')
    check('semantic_limit_detected',misleading['measurement_words'],{'warning':'Keyword fires on negation. Therefore this feature MUST be labeled word presence, never evidence of a real experiment.'})
    if (ROOT/'detail-index.json').exists():
        from bs4 import BeautifulSoup
        real=[]
        for row in json.loads((ROOT/'detail-index.json').read_text(encoding='utf8')):
            raw=json.loads((ROOT/row['source']).read_text(encoding='utf8'))['response']['article']['body_html']
            f=body_features(raw); soup=BeautifulSoup(raw,'html.parser')
            real.append({'id':row['id'],'pass':f['code_blocks']==len(soup.find_all('pre')) and f['images']==len(soup.find_all('img')) and f['tables']==len(soup.find_all('table'))})
        check('real_html_independent_parser',all(x['pass'] for x in real),real)
    if args.live:
        plan=json.loads((ROOT/'sampling-plan.json').read_text(encoding='utf8'))
        first=plan['queries'][0]
        before=(ROOT/'coverage.json').read_text(encoding='utf8')
        cached=Client()
        collect(cached,{'queries':[first]},False)
        check('real_cache_no_network',cached.network==0 and cached.cached==6,{'network':cached.network,'hits':cached.cached})
        fresh=Client(refresh=True)
        collect(fresh,{'queries':[first]},True)
        cov=json.loads((ROOT/'coverage.json').read_text(encoding='utf8'))
        check('real_incremental_refresh_then_overlap',fresh.network>=1 and cov['coverage'][0]['terminal']=='known_page_overlap_incremental_new_content_only',{'network':fresh.network,'coverage':cov})
        (ROOT/'coverage.json').write_text(before,encoding='utf8')
    write(ROOT/'ruler_check.json',{'checks':checks,'all_passed':all(c['passed'] for c in checks),'boundary':'Mechanical and lexical features calibrated; semantic usefulness requires qualitative review. Independent parser check requires beautifulsoup4.'})
    print(json.dumps({'passed':sum(c['passed'] for c in checks),'checks':len(checks)}))
    if not all(c['passed'] for c in checks):raise SystemExit(1)

if __name__=='__main__':main()
