"""Recomputable descriptive analysis; no exposure data or causal claims."""
import argparse
from collections import Counter, defaultdict
import datetime as dt
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import random
import re
import statistics as st
from collect import ROOT, write

TITLE_RULES = {
    'question': r'[?？]|なぜ|どうして',
    'number': r'[0-9０-９]',
    'trial_or_comparison': r'検証|比較|試し|試す|試した|使って|やって|実験|計測|測定|ベンチマーク',
    'failure_or_limit': r'失敗|限界|落とし穴|罠|ハマ|できない|効かない|問題|注意|やめ',
    'guide_or_summary': r'入門|まとめ|完全|ガイド|解説|とは|仕組み|使い方',
    'firsthand_build': r'作った|作って|開発した|導入した|運用|実装した|実装して',
}

def date(value):
    return dt.datetime.fromisoformat(value)

def load():
    rows = {}
    memberships = []
    for path in sorted((ROOT / 'indexes').glob('*.json')):
        idx = json.loads(path.read_text(encoding='utf-8'))
        q = idx['query']
        for id_, value in idx['articles'].items():
            a = value['article']
            rows[id_] = {**a, 'source': value['source']}
            memberships.append({'id': id_, 'topic': q.get('topicname', 'global'), 'order': q['order']})
    return rows, memberships

def select():
    rows, memberships = load()
    now = dt.datetime.now(dt.timezone.utc)
    used, chosen, pairs = set(), [], []
    rng = random.Random(20260925)
    for topic in sorted({x['topic'] for x in memberships if x['order'] == 'latest'}):
        pool = [rows[x['id']] for x in memberships if x['topic'] == topic and x['order'] == 'latest'
                and (now-date(rows[x['id']]['published_at'])).days >= 7]
        # Extremes are purposefully selected for contrast; this is not prevalence estimation.
        high = sorted(pool, key=lambda a: (-a['liked_count'], a['id']))
        lows = sorted(pool, key=lambda a: (a['liked_count'], a['id']))
        count = 0
        for a in high:
            if a['id'] in used or a['liked_count'] < 2:
                continue
            candidates = [b for b in lows if b['id'] not in used and b['id'] != a['id']
                          and b['liked_count'] < a['liked_count']
                          and b['published_at'][:7] == a['published_at'][:7]
                          and abs((date(b['published_at'])-date(a['published_at'])).total_seconds()) <= 14*86400]
            if not candidates:
                continue
            low_floor = candidates[0]['liked_count']
            candidates = [b for b in candidates if b['liked_count'] == low_floor]
            b = rng.choice(candidates)
            pair_id = f'{topic}-{count+1:02d}'
            pairs.append({'pair': pair_id, 'topic': topic, 'high_id': a['id'], 'low_id': b['id'],
                          'gap_days': abs((date(a['published_at'])-date(b['published_at'])).total_seconds())/86400,
                          'same_author': a['user']['id'] == b['user']['id']})
            for item, group in [(a, 'higher'), (b, 'lower')]:
                used.add(item['id'])
                chosen.append({'id': item['id'], 'slug': item['slug'], 'topic': topic, 'group': group, 'pair': pair_id})
            count += 1
            if count == 12:
                break
    historic = sorted([rows[x['id']] for x in memberships if x['order'] == 'alltime'], key=lambda a: (-a['liked_count'],a['id']))
    # Supplement underfilled pair budget with explicit historical examples.
    for a in historic:
        if len(chosen) >= 160:
            break
        if a['id'] in used:
            continue
        used.add(a['id'])
        chosen.append({'id': a['id'], 'slug': a['slug'], 'topic': 'history', 'group': 'historical_example', 'pair': None})
    write(ROOT/'selection.json', chosen)
    write(ROOT/'pairs.json', pairs)
    print(json.dumps({'selected':len(chosen), 'pairs':len(pairs), 'groups':dict(Counter(x['group'] for x in chosen))}))

class Body(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = Counter()
        self.parts = []
        self.paragraphs = []
        self.p = None
        self.exclude = 0

    def handle_starttag(self, tag, attrs):
        self.tags[tag] += 1
        if tag in ('script','style'):
            self.exclude += 1
        if tag == 'p':
            self.p = []
        if tag in ('p','h1','h2','h3','li','tr','pre'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script','style'):
            self.exclude -= 1
        if tag == 'p' and self.p is not None:
            self.paragraphs.append(''.join(self.p))
            self.p = None

    def handle_data(self, data):
        if not self.exclude:
            self.parts.append(data)
            if self.p is not None:
                self.p.append(data)

def body_features(html):
    parser = Body()
    parser.feed(html)
    text = ''.join(parser.parts)
    opening = '\n'.join(parser.paragraphs)[:500]
    return {'code_blocks':parser.tags['pre'],'images':parser.tags['img'],'tables':parser.tags['table'],
            'paragraphs':parser.tags['p'],'headings':sum(parser.tags[x] for x in ['h1','h2','h3']),
            'measurement_words':bool(re.search(r'検証|実験|計測|測定|ベンチマーク|正解率|成功率',text)),
            'limitations_words':bool(re.search(r'限界|制約|注意点|課題|失敗|ただし|一方で',text)),
            'opening_problem_words':bool(re.search(r'困|課題|問題|悩|面倒|失敗|できな|なぜ|どう',opening)),
            'opening_result_words':bool(re.search(r'結論|結果|わかった|分かった|できた|改善|削減',opening)),
            'text':text,'opening':opening}

def summary(items):
    likes = [a['liked_count'] for a in items]
    return {'n':len(items), 'median_likes':st.median(likes) if likes else None,
            'mean_likes':st.mean(likes) if likes else None,
            'median_bookmarks':st.median(a['bookmarked_count'] for a in items) if items else None,
            'median_comments':st.median(a['comments_count'] for a in items) if items else None,
            'zero_share':sum(x==0 for x in likes)/len(likes) if likes else None}

def analyze():
    rows, memberships = load()
    observed = date(json.loads((ROOT/'coverage.json').read_text(encoding='utf8'))['observed_at'])
    for a in rows.values():
        a['title_features'] = {k:bool(re.search(v,a['title'])) for k,v in TITLE_RULES.items()}
        a['age_days'] = (observed-date(a['published_at'])).total_seconds()/86400
    topic_stats = []
    for topic, order in sorted({(x['topic'],x['order']) for x in memberships}):
        aa=[rows[x['id']] for x in memberships if x['topic']==topic and x['order']==order]
        topic_stats.append({'topic':topic,'order':order,**summary(aa),'earliest':min(a['published_at'] for a in aa),'latest':max(a['published_at'] for a in aa)})
    recent_ids = {x['id'] for x in memberships if x['order']=='latest'}
    recent = [rows[x] for x in recent_ids if rows[x]['age_days']>=7]
    feature_stats = []
    # Each topic-month comparison has both groups; descriptive weighted difference, not causal adjustment.
    for feature in TITLE_RULES:
        cells=defaultdict(list)
        for m in memberships:
            a=rows[m['id']]
            if m['order']=='latest' and a['age_days']>=7:
                cells[(m['topic'],a['published_at'][:7])].append(a)
        contrasts=[]
        for (topic,month),aa in cells.items():
            yes=[a for a in aa if a['title_features'][feature]]
            no=[a for a in aa if not a['title_features'][feature]]
            if len(yes)>=5 and len(no)>=5:
                # Equal-author weighted means limit prolific-author domination, not follower confounding.
                def author_mean(items):
                    group=defaultdict(list)
                    for a in items:group[a['user']['id']].append(math.log1p(a['liked_count']))
                    return st.mean(st.mean(v) for v in group.values())
                contrasts.append({'topic':topic,'month':month,'yes':summary(yes),'no':summary(no),
                                  'log1p_difference':st.mean(math.log1p(a['liked_count']) for a in yes)-st.mean(math.log1p(a['liked_count']) for a in no),
                                  'equal_author_log1p_difference':author_mean(yes)-author_mean(no)})
        feature_stats.append({'feature':feature,'yes':summary([a for a in recent if a['title_features'][feature]]),
                              'no':summary([a for a in recent if not a['title_features'][feature]]),'topic_month_cells':contrasts})
    lengths=[]
    for lower,upper in [(0,2000),(2000,5000),(5000,10000),(10000,20000),(20000,float('inf'))]:
        lengths.append({'range':f'{lower}-{upper}',**summary([a for a in recent if lower<=a['body_letters_count']<upper])})
    detail_features=[]
    for d in json.loads((ROOT/'detail-index.json').read_text(encoding='utf8')):
        raw=json.loads((ROOT/d['source']).read_text(encoding='utf8'))
        a=raw['response']['article']
        features=body_features(a['body_html'])
        # Full text remains private raw evidence. Derived excerpts only for local qualitative inspection.
        text=features.pop('text')
        write(ROOT/'reading'/f'{a["id"]}.json',{'id':a['id'],'url':'https://zenn.dev'+a['path'],'title':a['title'],'text':text,'source':d['source']})
        detail_features.append({**d,'title':a['title'],'url':'https://zenn.dev'+a['path'],'liked_count':a['liked_count'],
                                'published_at':a['published_at'],'author_id':a['user']['id'],**features})
    body_stats=[]
    for feature in ['code_blocks','images','tables','measurement_words','limitations_words','opening_problem_words','opening_result_words']:
        groups={}
        for group in ['higher','lower','historical_example']:
            aa=[a for a in detail_features if a['group']==group]
            groups[group]={'n':len(aa),'positive':sum(bool(a[feature]) for a in aa),'share':sum(bool(a[feature]) for a in aa)/len(aa) if aa else None}
        body_stats.append({'feature':feature,'groups':groups})
    write(ROOT/'metadata.json', {'articles':list(rows.values()),'memberships':memberships})
    write(ROOT/'body-features.json',detail_features)
    write(ROOT/'statistics.json',{'observed_at':observed.isoformat(),'unique_articles':len(rows),'recent_mature_unique':len(recent),
                                 'topic_stats':topic_stats,'title_features':feature_stats,'length_groups':lengths,'body_features':body_stats})
    print(json.dumps({'unique_articles':len(rows),'recent_mature':len(recent),'details':len(detail_features)}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['select','analyze']);args=p.parse_args()
    select() if args.command=='select' else analyze()
