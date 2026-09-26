"""Render actual saved results and execute the exact Python blocks in round-two drafts."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager

HERE = Path(__file__).resolve().parent
PIPE = HERE.parents[2]

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def source(path):
    return {'path':path.relative_to(PIPE).as_posix(),'sha256':sha(path)}

font_path=Path('C:/Windows/Fonts/YuGothR.ttc')
font_manager.fontManager.addfont(str(font_path))
plt.rcParams.update({'font.family':font_manager.FontProperties(fname=str(font_path)).get_name(),
                     'font.size':12,'axes.unicode_minus':False,'svg.fonttype':'path'})

def figure(run, filename, labels, values, legends, title, ylabel, maximum, note):
    target=run/'figures-round2'
    target.mkdir(exist_ok=True)
    fig,ax=plt.subplots(figsize=(10.8,5.8))
    x=list(range(len(labels)))
    for offset,values_,legend,color in zip([-.19,.19],values,legends,['#24678a','#dc8040']):
        bars=ax.bar([n+offset for n in x],values_,width=.35,label=legend,color=color)
        ax.bar_label(bars,padding=5,fontsize=14)
    ax.set_xticks(x,labels)
    ax.set_ylabel(ylabel)
    ax.set_ylim(0,maximum)
    ax.set_title(title,pad=19,fontweight='bold')
    ax.legend(loc='upper center',bbox_to_anchor=(.5,1.0),ncol=2,frameon=False)
    ax.spines[['top','right']].set_visible(False)
    ax.grid(axis='y',alpha=.16)
    ax.set_axisbelow(True)
    fig.text(.07,.025,note,fontsize=10,va='bottom')
    fig.tight_layout(rect=(0,.1,1,1))
    for suffix in ['png','svg']:
        fig.savefig(target/(filename+'.'+suffix),dpi=180)
    plt.close(fig)

def main():
    result={'started_at':dt.datetime.now(dt.timezone.utc).isoformat(),'sources':[], 'article_code':[], 'checks':[]}
    retrieval=PIPE/'runs/retrieval-v4'
    review=PIPE/'runs/review-behavior'
    raw_path=retrieval/'results/experiment/result.json'
    raw=read(raw_path)
    metrics=read(retrieval/'results/metrics.json')['metrics']
    for mode in ['body','body_metadata']:
        for row in raw['rows']:
            relevant=set(row['relevant_paths'])
            ranks=[i for i,doc in enumerate(row[mode]['ranking'],1) if doc['path'] in relevant]
            rank=min(ranks) if ranks else None
            assert rank==row[mode]['first_relevant_rank']
            assert int(rank==1)==row[mode]['hit1']
            assert int(rank is not None and rank<=3)==row[mode]['hit3']
        for name in ['hit1','hit3']:
            assert sum(row[mode][name] for row in raw['rows'])==metrics[mode+'_'+name]['value']
    result['checks'].append({'name':'ranking_recomputed_independently','question_rows':len(raw['rows']),'modes':['body','body_metadata'],'passed':True})
    figure(retrieval,'retrieval-results',['先頭で見つかる\n（順位の改善）','上位 3 件で見つかる\n（元の主指標）'],
           [[metrics[m+'_'+h]['value'] for h in ['hit1','hit3']] for m in ['body','body_metadata']],
           ['本文のみ','見出し・パスを加重'],'関連記事は前へ。見つかる質問の数は同じ。','該当する質問数',34,
           f"固定した技術記事 {raw['documents']} 本・質問 {len(raw['rows'])} 問。保存済みの各質問の順位から集計。\n同じ題材での比較であり、検索時間の短縮を測った図ではありません。")
    rm=read(review/'results/metrics.json')['metrics']
    accounting=read(review/'results/original-accounting.json')
    for mode in ['generic','skills']:
        assert accounting['groups'][mode]['primary']==rm['original_'+mode+'_primary']['value']
    result['checks'].append({'name':'review_score_matches_original_accounting','passed':True})
    figure(review,'review-results',['元の自動採点','報告可否の判断','事後の内容確認\n（別の AI・非盲検）'],
           [[rm['original_'+m+'_'+k]['value'] for k in ['primary','decision','semantic']] for m in ['generic','skills']],
           ['通常の依頼','証拠ルールを追加'],'得点と、回答内容の妥当性を分けて見る','各条件で該当する回答数',30,
           '各条件の分母は 24 回答。右の事後判断は、左の元得点を置き換えていません。\n異なる評価軸の比較であり、モデルの性能向上を示す図ではありません。')
    paths=[raw_path,retrieval/'results/metrics.json',review/'results/metrics.json',review/'results/original-accounting.json',review/'results/snapshots/semantic-review.json',review/'results/snapshots/reference_answers.json',review/'results/study/sessions/c02_generic_0/answer.txt']
    hashes={str(path):sha(path) for path in paths}
    for run in [retrieval,review]:
        draft=run/'article-round2.md'
        blocks=re.findall(r'```python\n(.*?)\n```',draft.read_text(encoding='utf8'),re.S)
        for index,code in enumerate(blocks):
            script=HERE/(run.name+f'-snippet-{index}.py')
            script.write_text(code+'\n',encoding='utf8')
            completed=subprocess.run([sys.executable,str(script)],cwd=run,capture_output=True,text=True,encoding='utf8')
            stdout=HERE/(run.name+f'-snippet-{index}.stdout.txt')
            stderr=HERE/(run.name+f'-snippet-{index}.stderr.txt')
            stdout.write_text(completed.stdout,encoding='utf8');stderr.write_text(completed.stderr,encoding='utf8')
            result['article_code'].append({'run':run.name,'article':source(draft),'code':source(script),'stdout':source(stdout),'stderr':source(stderr),'exit_code':completed.returncode})
            assert completed.returncode==0,completed.stderr
            expected=re.findall(r'```text\n(.*?)\n```',draft.read_text(encoding='utf8'),re.S)[index]
            assert completed.stdout.strip()==expected.strip(),{'actual':completed.stdout,'article':expected}
    assert all(sha(Path(path))==digest for path,digest in hashes.items())
    result['checks'].append({'name':'original_sources_unchanged','passed':True})
    result['sources']=[source(path) for path in paths]
    result['renderer']=source(Path(__file__))
    result['font']=str(font_path)
    result['finished_at']=dt.datetime.now(dt.timezone.utc).isoformat()
    (HERE/'render-verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'checks':result['checks'],'code_blocks':len(result['article_code']),'figure_count':2},ensure_ascii=False))

if __name__=='__main__':main()
