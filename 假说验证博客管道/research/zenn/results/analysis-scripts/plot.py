"""Create exportable descriptive figures from the saved statistics."""
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from collect import ROOT

stats=json.loads((ROOT/'statistics.json').read_text(encoding='utf8'))
items=[x for x in stats['body_features'] if x['feature'] in ['images','code_blocks','tables']]
fig,ax=plt.subplots(figsize=(8,4.5))
x=list(range(len(items)))
for offset,group,label,color in [(-.18,'higher','Higher-like articles','#2d7eae'),(.18,'lower','Lower-like articles','#a9a9a9')]:
    counts=[r['groups'][group]['positive'] for r in items]
    bars=ax.bar([i+offset for i in x],counts,width=.34,label=label,color=color)
    ax.bar_label(bars,padding=3)
ax.set_xticks(x,[r['feature'].replace('_',' ').title() for r in items])
ax.set_ylabel('Articles with feature (out of 65 per group)')
ax.set_ylim(0,65)
ax.set_title('Zenn body features: 65 topic/month matched pairs')
ax.legend(frameon=False)
ax.spines[['top','right']].set_visible(False)
fig.text(.02,.02,'Selected extremes, not a representative sample. Association is not causation. Snapshot: 2026-09-25.',fontsize=8)
fig.tight_layout(rect=(0,.05,1,1))
(ROOT/'figures').mkdir(exist_ok=True)
fig.savefig(ROOT/'figures'/'body-features.png',dpi=180)
fig.savefig(ROOT/'figures'/'body-features.svg')
