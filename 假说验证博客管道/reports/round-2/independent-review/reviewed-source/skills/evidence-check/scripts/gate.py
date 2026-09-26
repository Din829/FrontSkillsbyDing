"""Check declared measurements against recorded facts; judgments follow policy.json."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
import re
import subprocess

POLICY_PATH = Path(__file__).resolve().parents[3] / "policy.json"
NUMBER = re.compile(r"[+\-−]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:[eE][+\-]?\d+)?|[+\-−]?\.\d+")
IGNORABLE = [
    ("url", re.compile(r"https?://[^\s<>]+")),
    ("version", re.compile(r"\bv\d+(?:\.\d+)+(?:[-+][\w.-]+)?\b", re.I)),
    ("date", re.compile(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b|\b\d{4}\s*年")),
    ("identifier", re.compile(r"\b[A-Za-z][A-Za-z0-9_]*(?:[-.][A-Za-z0-9_]+)*\b")),
    ("structure", re.compile(r"^\s*(?:#{1,6}\s+)?\d+[.)、]\s", re.M)),
]

def require_type(value, expected, label):
    if not isinstance(value, expected):
        raise ValueError(f"{label} must be {expected.__name__}")
    return value

def require_text(value, label):
    require_type(value, str, label)
    if not value.strip():
        raise ValueError(label + " must be nonempty")
    return value

def read_json(path):
    return require_type(json.loads(Path(path).read_text(encoding="utf-8-sig")), dict, str(path))

def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def scan(text):
    """Historical token indices are retained; ignored metadata stays visible."""
    spans = [(reason, m.start(), m.end()) for reason, pattern in IGNORABLE for m in pattern.finditer(text)]
    return [{"index": i, "token": m.group(), "line": text.count("\n", 0, m.start()) + 1,
             "start": m.start(), "end": m.end(),
             "ignore_reason": next((reason for reason, start, end in spans if start <= m.start() and m.end() <= end), None)}
            for i, m in enumerate(NUMBER.finditer(text))]

def decimal(value):
    if isinstance(value, bool):
        raise ValueError("Boolean is not a numeric metric")
    result = Decimal(str(value).replace(",", "").replace("−", "-"))
    if not result.is_finite():
        raise ValueError("Nonfinite numeric value")
    return result

class Conflict(ValueError):
    def __init__(self, code, detail, category="numeric_mismatch"):
        super().__init__(detail)
        self.code, self.category = code, category

class Gate:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.issues, self.run, self.policy = [], {}, {}
        self.incomplete, self.measured_claims = False, set()
        self.ruler = {"recorded_status": None, "path": None}
        self.checked_measurements = 0
        self.location = {}
        self.policy_sha256 = None
        self.guarded("policy_unavailable", self.load_policy)

    def load_policy(self):
        self.policy = read_json(POLICY_PATH)
        require_type(self.policy["fatal_categories"], list, "fatal_categories")
        self.policy_sha256 = sha(POLICY_PATH)

    def issue(self, code, detail, category="evidence_gap", *, incomplete=False, location=None):
        where = self.location if location is None else location
        semantic = {"code": code, "document": where.get("document"), "claim_id": where.get("claim_id"), "ref": where.get("ref")}
        stable_id = code + ":" + hashlib.sha256(json.dumps(semantic, sort_keys=True).encode()).hexdigest()[:16]
        if not any(issue["id"] == stable_id for issue in self.issues):
            self.issues.append({"id": stable_id, "code": code, "category": category,
                                "severity": "fatal" if category in self.policy.get("fatal_categories", []) else "warning",
                                "location": dict(where), "detail": detail})
        self.incomplete |= incomplete

    def guarded(self, code, action):
        try:
            return action()
        except Conflict as exc:
            self.issue(exc.code, str(exc), exc.category)
        except (OSError, ValueError, KeyError, TypeError, IndexError, ArithmeticError) as exc:
            self.issue(code, str(exc), incomplete=True)
        return None

    def inside(self, name, results=True):
        path = (self.root / require_text(name, "artifact path")).resolve()
        boundary = (self.root / "results") if results else self.root
        if not path.is_relative_to(boundary.resolve()):
            raise Conflict("path_outside_scope", "Path escapes its allowed directory: " + name, "authorization")
        return path

    def artifact(self, ref, results=True):
        require_type(ref, dict, "artifact reference")
        path = self.inside(ref["path"], results)
        actual = sha(path)
        if not ref.get("sha256"):
            self.issue("hash_missing", "No recorded hash for " + ref["path"])
        elif actual != ref["sha256"]:
            self.issue("hash_drift", "Recorded hash differs; compare actual fields: " + ref["path"], "record_note")
        return path

    def metric(self, ref):
        self.location["ref"] = {"path": ref.get("path"), "pointer": ref.get("pointer")}
        source = read_json(self.artifact(ref))
        if source["run_id"] != self.run["run_id"] or ref["run_id"] != self.run["run_id"]:
            raise Conflict("source_run_mismatch", "Metric belongs to a different run")
        origin = require_type(source.get("origin", {}), dict, "source origin")
        if origin.get("kind") == "external":
            self.artifact(origin["snapshot"])
        node = source
        pointer = require_text(ref["pointer"], "JSON pointer")
        if not pointer.startswith("/"):
            raise ValueError("JSON pointer must begin with /")
        for key in pointer[1:].split("/"):
            key = key.replace("~1", "/").replace("~0", "~")
            if isinstance(node, list):
                if not re.fullmatch(r"0|[1-9][0-9]*", key):
                    raise ValueError("JSON Pointer array index must be a nonnegative integer without leading zeros")
                node = node[int(key)]
            else:
                node = node[key]
        if node["unit"] != ref["unit"]:
            raise Conflict("source_unit_mismatch", "Metric unit differs from referenced unit")
        return decimal(node["value"]), node["unit"]

    def number_value(self, binding):
        if "ref" in binding:
            return self.metric(binding["ref"])
        calc = binding["calculation"]
        inputs = [self.metric(ref) for ref in calc["inputs"]]
        if not inputs:
            raise ValueError("Calculation has no inputs")
        if len({unit for _, unit in inputs}) != 1:
            raise Conflict("calculation_unit_mismatch", "Calculation inputs have incompatible units")
        values, op = [value for value, _ in inputs], calc["op"]
        if op == "sum":
            return sum(values), inputs[0][1]
        if op == "mean":
            return sum(values) / len(values), inputs[0][1]
        if op == "difference" and len(values) == 2:
            return values[0] - values[1], inputs[0][1]
        if op in {"ratio", "percent", "relative_change_percent"} and len(values) == 2:
            value = ((values[0] - values[1]) if op == "relative_change_percent" else values[0]) / values[1]
            return (value, "ratio") if op == "ratio" else (value * 100, "percent")
        raise ValueError("Unsupported operation or wrong input count: " + str(op))

    def number_check(self, binding, tokens, claims, text):
        index = binding["index"]
        if type(index) is not int or index < 0:
            raise ValueError("Numeric index must be a nonnegative integer")
        token = tokens[index]
        if binding["token"] != token["token"]:
            raise ValueError("Binding token changed; review the draft-to-claim mapping")
        claim = claims[binding["claim_id"]]
        positions = list(re.finditer(re.escape(claim["text"]), text))
        if not any(m.start() <= token["start"] and token["end"] <= m.end() for m in positions):
            raise ValueError("Number occurrence is outside its associated claim")
        value, unit = self.number_value(binding)
        if unit != binding["unit"]:
            raise Conflict("display_unit_mismatch", "Displayed unit differs from source/calculation unit")
        if "decimals" in binding:
            places = binding["decimals"]
            if type(places) is not int or places < 0:
                raise ValueError("decimals must be a nonnegative integer")
            value = value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
        if value != decimal(token["token"]):
            raise Conflict("value_mismatch", f"Source value {value} differs from stated value {token['token']}")
        self.checked_measurements += 1

    def document_checks(self, document):
        self.location = {"document": document["draft"]["path"]}
        draft = self.artifact(document["draft"], results=False)
        text = draft.read_text(encoding="utf-8-sig")
        if not text.strip():
            raise ValueError("Document is empty")
        data = read_json(self.inside(document["claims"], results=False))
        if data["run_id"] != self.run["run_id"]:
            self.issue("claims_run_mismatch", "Claims file belongs to another run; inspect numeric sources", incomplete=True)
        if data.get("draft_sha256") != sha(draft):
            self.issue("draft_revision_drift", "Draft revision changed; current bindings will be checked where still resolvable", "record_note")
        claims = require_type(data.get("claims", []), list, "claims")
        by_id = {claim["id"]: claim for claim in claims}
        if len(by_id) != len(claims):
            self.issue("claim_duplicate", "Duplicate claim IDs need semantic review")
        for claim in claims:
            self.location = {"document": document["draft"]["path"], "claim_id": claim["id"]}
            if claim.get("level") == "measured":
                self.measured_claims.add((document["draft"]["path"], claim["id"]))
            if not claim.get("text") or claim["text"] not in text:
                self.issue("claim_text_drift", "Claim text is absent from current document", incomplete=True)
        tokens = scan(text)
        bindings = require_type(data.get("numbers", []), list, "numbers")
        mapped = set()
        for binding in bindings:
            mapped.add(binding.get("index"))
            if binding.get("kind") != "measurement":
                continue
            self.location = {"document": document["draft"]["path"], "claim_id": binding.get("claim_id")}
            self.guarded("measurement_unverifiable", lambda binding=binding: self.number_check(binding, tokens, by_id, text))
        self.location = {"document": document["draft"]["path"]}
        candidates = [t for t in tokens if t["index"] not in mapped and not t["ignore_reason"]]
        if candidates:
            self.issue("unclassified_numbers", "Semantic review candidates: " + ", ".join(f"{t['index']}:{t['token']}" for t in candidates), "record_note")

    def execution_checks(self):
        self.location = {}
        reference = require_type(self.run["execution"], dict, "execution reference")
        self.location = {"ref": {"path": reference.get("path")}}
        record = read_json(self.artifact(reference))
        if record["run_id"] != self.run["run_id"]:
            self.issue("execution_run_mismatch", "Execution record belongs to another run", incomplete=True)
            return
        for key in ("stdout", "stderr"):
            self.guarded("execution_log_unavailable", lambda key=key: self.artifact(record[key]))
        exit_code = record["exit_code"]
        if type(exit_code) is not int:
            raise ValueError("execution.exit_code must be an integer")
        claims_success = self.run.get("execution_claim") == "succeeded" or (self.measured_claims and self.run.get("execution_claim") not in ("failed", "not_run"))
        if exit_code != 0:
            if claims_success:
                self.issue("false_success", "Recorded execution failed while the report claims measured success", "false_success")
            else:
                self.issue("execution_failed_recorded", "Execution failure recorded; failure report can continue", "record_note")

    def ruler_checks(self):
        reference = self.run.get("ruler")
        if not reference:
            self.issue("ruler_not_recorded", "No ruler record supplied; reviewer judges the measurement method", "record_note")
            return
        require_type(reference, dict, "ruler reference")
        self.location = {"ref": {"path": reference.get("path")}}
        path = self.artifact(reference)
        self.ruler = {"path": reference["path"], "recorded_status": read_json(path).get("status") if path.suffix == ".json" else "see_document"}
        if self.ruler["recorded_status"] != "passed":
            self.issue("ruler_record_note", "Ruler record status: " + str(self.ruler["recorded_status"]) + "; no scientific validity decision made", "record_note")

    def report(self):
        fatal = any(i["severity"] == "fatal" for i in self.issues)
        status = "blocked" if fatal else ("incomplete" if self.incomplete else ("warnings" if self.issues else "traceable"))
        return {"run_id": self.run.get("run_id"), "status": status, "issues": self.issues,
                "ruler": self.ruler, "checked_measurements": self.checked_measurements,
                "policy_sha256": self.policy_sha256, "scope": "Declared-number bookkeeping only; scientific validity and claim completeness require semantic review."}

    def check(self):
        self.guarded("manifest_unavailable", lambda: setattr(self, "run", read_json(self.root / "run.json")))
        self.guarded("run_id_missing", lambda: require_text(self.run["run_id"], "run_id"))
        documents = self.run.get("documents")
        if not isinstance(documents, list) or not documents:
            self.issue("documents_missing", "No documents supplied for checking", incomplete=True)
        else:
            for document in documents:
                self.location = {}
                self.guarded("document_unavailable", lambda document=document: self.document_checks(document))
        self.guarded("execution_unavailable", self.execution_checks)
        self.location = {}
        self.guarded("ruler_unavailable", self.ruler_checks)
        return self.report()

def capture(root, command):
    check = Gate(root)
    check.guarded("capture_manifest_unavailable", lambda: setattr(check, "run", read_json(check.root / "run.json")))
    check.guarded("capture_run_id_missing", lambda: require_text(check.run["run_id"], "run_id"))
    budget = check.run.get("budget", {})
    if isinstance(budget, dict) and budget.get("status") == "exceeded":
        check.issue("budget_exceeded", "No process launched; reporting existing evidence remains possible", "authorization")
    if check.incomplete or any(i["severity"] == "fatal" for i in check.issues):
        return check.report()
    results = check.root / "results"
    results.mkdir(parents=True, exist_ok=True)
    for name in ("execution.json", "stdout.log", "stderr.log"):
        if (results / name).exists():
            check.issue("capture_would_overwrite", "Use a new run to preserve prior execution evidence", "authorization")
            return check.report()
    record = {"run_id": check.run["run_id"], "command": command, "started_at": datetime.now(timezone.utc).isoformat()}
    with (results / "stdout.log").open("wb") as stdout, (results / "stderr.log").open("wb") as stderr:
        process = subprocess.run(command, cwd=check.root, stdout=stdout, stderr=stderr, check=False)
    record.update(exit_code=process.returncode, finished_at=datetime.now(timezone.utc).isoformat())
    for key in ("stdout", "stderr"):
        path = results / (key + ".log")
        record[key] = {"path": path.relative_to(check.root).as_posix(), "sha256": sha(path)}
    write_json(results / "execution.json", record)
    return record

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="action", required=True)
    cmd = subs.add_parser("scan")
    cmd.add_argument("draft")
    cmd.add_argument("--candidates", action="store_true")
    cmd = subs.add_parser("check")
    cmd.add_argument("run_dir")
    cmd.add_argument("--strict", action="store_true")
    cmd.add_argument("--output")
    cmd = subs.add_parser("capture")
    cmd.add_argument("run_dir")
    cmd.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.action == "scan":
        result = scan(Path(args.draft).read_text(encoding="utf-8-sig"))
        if args.candidates:
            result = [token for token in result if not token["ignore_reason"]]
    elif args.action == "capture":
        command = args.command[1:] if args.command[:1] == ["--"] else args.command
        if not command:
            parser.error("capture requires a command")
        result = capture(args.run_dir, command)
    else:
        result = Gate(args.run_dir).check()
        if args.output:
            write_json(args.output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.action == "check":
        return 2 if args.strict and result["status"] == "blocked" else 0
    if args.action == "capture":
        return 2 if result.get("status") == "blocked" else (1 if result.get("exit_code", 0) != 0 else 0)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
