"""Public Zenn snapshots. Standard library only; no login, keys or publication."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import time
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()

def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')

class Client:
    def __init__(self, delay=1.1, refresh=False):
        self.delay, self.refresh, self.last = delay, refresh, 0.0
        self.network = self.cached = 0
        self.events = []

    def get(self, path, params=None):
        url = 'https://zenn.dev' + path
        if params:
            url += '?' + urllib.parse.urlencode(sorted(params.items()))
        key = hashlib.sha256(url.encode()).hexdigest()[:24]
        cache = ROOT / 'raw' / (key + '.json')
        if cache.exists() and not self.refresh:
            self.cached += 1
            data = json.loads(cache.read_text(encoding='utf-8'))
            self.events.append({'url': url, 'cache': True, 'path': str(cache.relative_to(ROOT))})
            return data['response'], str(cache.relative_to(ROOT))
        time.sleep(max(0, self.delay - (time.monotonic() - self.last)))
        self.last = time.monotonic()
        req = urllib.request.Request(url, headers={'User-Agent': 'BlogResearch/0.1 (public article analysis; low-rate)'})
        try:
            with urllib.request.urlopen(req, timeout=45) as response:
                body = response.read().decode('utf-8')
                content = json.loads(body) if 'json' in response.headers.get('Content-Type', '') else body
                snapshot = {'url': url, 'observed_at': now(), 'status': response.status,
                            'headers': dict(response.headers), 'response': content}
        except Exception as exc:
            self.events.append({'url': url, 'cache': False, 'failed_at': now(),
                                'error_type': type(exc).__name__, 'message': str(exc)})
            raise
        if cache.exists():
            old = json.loads(cache.read_text(encoding='utf-8'))
            stamp = old['observed_at'].replace(':', '').replace('.', '')
            write(ROOT / 'raw' / 'history' / (key + '-' + stamp + '.json'), old)
        write(cache, snapshot)
        self.network += 1
        self.events.append({'url': url, 'cache': False, 'path': str(cache.relative_to(ROOT))})
        return content, str(cache.relative_to(ROOT))

def probe(client):
    variants = [
        {'order': 'latest', 'count': 10, 'page': 1, 'topicname': 'ai'},
        {'order': 'latest', 'count': 10, 'page': 1, 'topicname': 'rag'},
        {'order': 'latest', 'count': 10, 'page': 1, 'topicname': 'nonexistent-topic-20260925-zq'},
        {'order': 'latest', 'count': 100, 'page': 1, 'topicname': 'ai'},
        {'order': 'latest', 'count': 100, 'page': 2, 'topicname': 'ai'},
        {'order': 'liked_count', 'count': 100, 'page': 1, 'topicname': 'ai'},
        {'order': 'liked_count', 'count': 100, 'page': 1},
        {'order': 'alltime', 'count': 100, 'page': 1, 'topicname': 'ai'},
    ]
    result = []
    for params in variants:
        data, source = client.get('/api/articles', params)
        articles = data['articles']
        row = {'params': params, 'count_returned': len(articles), 'next_page': data.get('next_page'),
               'total_count': data.get('total_count'), 'source': source,
               'ids': [a['id'] for a in articles],
               'first': [{k: a.get(k) for k in ['slug', 'title', 'liked_count', 'published_at']} for a in articles[:3]],
               'last': [{k: a.get(k) for k in ['slug', 'liked_count', 'published_at']} for a in articles[-2:]]}
        result.append(row)
        print(json.dumps(row, ensure_ascii=True), flush=True)
    for path in ['/robots.txt', '/sitemaps/_index.xml', '/terms', '/guideline']:
        client.get(path)
    write(ROOT / 'probe.json', result)

def collect(client, plan, incremental):
    coverage = []
    for query in plan['queries']:
        target = query.get('sample_target')
        params = {k: v for k, v in query.items() if k != 'sample_target'}
        params.setdefault('page', 1)
        key = hashlib.sha256(json.dumps({k:v for k,v in params.items() if k != 'page'}, sort_keys=True).encode()).hexdigest()[:16]
        index_path = ROOT / 'indexes' / (key + '.json')
        prior = json.loads(index_path.read_text(encoding='utf-8')) if index_path.exists() else {'articles': {}}
        known = set(prior['articles'])
        seen, sources = set(), []
        terminal = None
        while True:
            data, source = client.get('/api/articles', params)
            batch = data['articles']
            ids = {str(a['id']) for a in batch}
            sources.append(source)
            if batch and ids <= seen:
                terminal = 'repeated_page_not_exhaustion'
                break
            seen.update(ids)
            for a in batch:
                prior['articles'][str(a['id'])] = {'article': a, 'source': source}
            next_page = data.get('next_page')
            if next_page is None:
                terminal = 'api_next_page_null_not_global_completeness'
                break
            if not batch:
                terminal = 'empty_page_with_next_page_inconsistent'
                break
            if incremental and params['order'] == 'latest' and known and ids <= known:
                terminal = 'known_page_overlap_incremental_new_content_only'
                break
            if target is not None and len(seen) >= target:
                terminal = 'declared_sample_target_reached'
                break
            params['page'] = next_page
        prior.update({'query': query, 'updated_at': now()})
        write(index_path, prior)
        coverage.append({'query': query, 'unique_seen_this_run': len(seen), 'stored_articles': len(prior['articles']),
                         'pages': len(sources), 'sources': sources, 'terminal': terminal, 'next_page': next_page,
                         'index': str(index_path.relative_to(ROOT))})
        print(json.dumps(coverage[-1], ensure_ascii=True), flush=True)
    record = {'observed_at': now(), 'incremental': incremental, 'coverage': coverage}
    write(ROOT / 'coverage.json', record)
    write(ROOT / 'coverage-history' / (dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%f') + '.json'), record)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('command', choices=['probe', 'collect', 'details'])
    p.add_argument('--plan', type=Path)
    p.add_argument('--selection', type=Path)
    p.add_argument('--delay', type=float, default=1.1)
    p.add_argument('--refresh', action='store_true')
    p.add_argument('--incremental', action='store_true')
    args = p.parse_args()
    if args.delay < 1:
        p.error('Public endpoint requests must be at least one second apart in this collector.')
    client = Client(args.delay, args.refresh)
    try:
        if args.command == 'probe':
            probe(client)
        elif args.command == 'collect':
            collect(client, json.loads(args.plan.read_text(encoding='utf-8')), args.incremental)
        else:
            selection = json.loads(args.selection.read_text(encoding='utf-8'))
            details = []
            for row in selection:
                data, source = client.get('/api/articles/' + row['slug'])
                details.append({**row, 'source': source})
                print(f'detail {len(details)}/{len(selection)} {row["slug"]}', flush=True)
            write(ROOT / 'detail-index.json', details)
    finally:
        stamp = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%f')
        write(ROOT / 'requests' / (stamp + '.json'), {'network_requests': client.network, 'cache_hits': client.cached, 'events': client.events})

if __name__ == '__main__':
    main()
