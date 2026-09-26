"""One-off source ledger for experimental numbers quoted in the delivery report.

Not a new pipeline gate or a rule for research design.
"""
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
report = (ROOT / "REPORT.md").read_text(encoding="utf-8")
calibration = "reports/round-2/calibration/retrieval-ruler.json"
smoke = "archive/round-2/compact-smoke/results/metrics.json"
entries = [
    ("正确文档排前的前三命中为 100%", calibration, "/summary/oracle/hit3", 100, 0, "100"),
    ("排末尾为 0%", calibration, "/summary/known_bad/hit3", 100, 0, "0"),
    ("随机排序均值为 14.88%", calibration, "/random_distribution/hit3/mean", 100, 2, "14.88"),
    ("原正文基线为 82.14%", calibration, "/summary/body/hit3", 100, 2, "82.14"),
    ("固定 CSV 计数得到 3/4、75%", smoke, "/metrics/ok/value", 1, 0, "3"),
    ("固定 CSV 计数得到 3/4、75%", smoke, "/metrics/total/value", 1, 0, "4"),
    ("固定 CSV 计数得到 3/4、75%", smoke, "/metrics/ok_percent/value", 1, 0, "75"),
]
ledger = []
for phrase, source, pointer, scale, decimals, displayed in entries:
    assert phrase in report, phrase
    path = ROOT / source
    value = json.loads(path.read_text(encoding="utf-8"))
    for key in pointer.strip("/").split("/"):
        value = value[key]
    calculated = (Decimal(str(value)) * scale).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
    assert calculated == Decimal(displayed), (phrase, calculated)
    ledger.append({"text": phrase, "level": "read", "displayed": displayed, "source": source,
                   "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "pointer": pointer,
                   "scale": scale, "decimals": decimals, "verified": True})
(ROOT / "reports/round-2/report-numbers.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"Verified {len(ledger)} quoted experimental values against explicit source fields")
