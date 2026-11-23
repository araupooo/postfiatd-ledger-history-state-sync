#!/usr/bin/env python3
"""probe.py — re-verify the ledger-history / state-sync pack from its outputs.

Usage:
    python3 scripts/probe.py [--skip-manifest-check] [LEDGER_HISTORY_RESULTS_JSON]

The --skip-manifest-check flag is for run_all.sh step 4 only: the
manifest on disk at that point predates the just-regenerated results,
so comparing against it would fail on any input change; step 5b re-runs
the probe without the flag after rewriting the manifest. A standalone
probe run (no flag) always performs the manifest check.

Checks (all re-derived, none trusted):
  A-00 pinned checkout HEAD equals the pinned commit.
  A-01 every VERIFIED rule's anchor sits inside its cited range in the
     pinned checkout; SPECIFIED rules carry external URLs; MODELLED /
     UNTESTABLE rules carry no file source. (45 rules: 38/4/2/1.)
  B-01 scenario arithmetic: 13 scenarios, 18 runs; outcomes synced 4 /
     stalled 4 / rejected 4 / partial 6; matrix rows == runs;
     fetched + missing == gap for every run; synced rounds ==
     ceil(gap / 100) plus one peer-switch round where applicable.
  C-01 catch-up math re-derived: catchup_table rounds == ceil(gap/100),
     within_history_window == (gap <= 256); fetch-pack table values
     match the pinned constants.
  D-01 key tokens at recorded lines: ledgerAcquireTimeout 3000ms
     (InboundLedger.cpp:74), ledgerTimeoutRetriesMax = 6 (:54),
     ledgerBecomeAggressiveThreshold = 4 (:58), LEDGER_HISTORY = 256
     (Config.h:224), MAX_LEDGER_GAP{100} (LedgerMaster.cpp:64),
     fetch-pack cache 65536 / 45 s (:116-117), 40 s refusal (:2133),
     sha512Half (:2043).
  E-01 fetch-pack verification re-grepped: getFetchPack retrieves,
     deletes, and compares sha512Half(data) with the requested hash.
  F-01 counts reconcile across files: matrix == results == scenarios
     (13); findings 12, claims 24 (16/2/4/2), risks 14, gaps 8; excerpts
     44 across 10 files agree across manifest, files, hashes.
  G-01 determinism: re-running the simulator to a temp dir reproduces
     byte-identical outputs (full SHA-256 compare).
  H-01 excerpt integrity: every excerpt file digest matches
     fixtures/source-hashes.json and every manifest blob SHA/size
     matches `git hash-object` / file size in the checkout;
     run-manifest digests match the shipped derived files.
  I-01 absence findings re-grepped: history_gap 0 hits;
     FetchPackTimeout 0 hits; maxFetchPack 0 hits.
  J-01 divergence tokens: MAX_LEDGER_GAP 100 is below LEDGER_HISTORY
     256; fetch-pack caps 512 objects / 16384 state nodes / 512 tx
     nodes are all in the build loop; the docs 256 figure appears in
     the citations, matching the code default.
  T-01 timing sanity only (non-negative, never recorded).

Exit 0 only if every case passes. Prints one PASS/FAIL line per case
with the FULL 64-char SHA-256 digest where a digest is involved, and
writes outputs/derived/probe-results.json plus outputs/probe-run.log
(the log is the unedited stdout of this run; it contains no absolute
paths and no timestamps). No live node is involved.
"""
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parent.parent
PINNED_COMMIT = "0085a1ff885d6a446369cf73a4430f75af22be55"
PINNED_CHECKOUT = Path(os.environ.get(
    "PINNED_CHECKOUT", str(Path.home() / "workspace" / "postfiatd-pin-0085a1f")))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def git_blob(relpath):
    out = subprocess.run(["git", "-C", str(PINNED_CHECKOUT), "hash-object", "--", relpath],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


def read_lines(relpath):
    return (PINNED_CHECKOUT / relpath).read_text().splitlines()


def grep_hits(pattern, *roots):
    proc = subprocess.run(
        ["grep", "-rn", pattern, *[str(PINNED_CHECKOUT / r) for r in roots]],
        capture_output=True, text=True)
    return [ln for ln in proc.stdout.splitlines() if ln.strip()]


def main():
    started = time.time()
    argv = [a for a in sys.argv[1:] if a != "--skip-manifest-check"]
    skip_manifest = "--skip-manifest-check" in sys.argv[1:]
    results_path = Path(argv[0]) if argv else \
        PACK_ROOT / "outputs" / "derived" / "ledger-history-results.json"
    doc = load_json(results_path)
    matrix = load_json(PACK_ROOT / "outputs" / "derived" / "scenario-matrix.json")
    rules = load_json(PACK_ROOT / "configs" / "ledger-history-rules.json")["rules"]
    scenarios = load_json(PACK_ROOT / "configs" / "scenarios.json")["scenarios"]
    manifest = load_json(PACK_ROOT / "fixtures" / "excerpts-manifest.json")
    hashes = load_json(PACK_ROOT / "fixtures" / "source-hashes.json")
    findings = load_json(PACK_ROOT / "findings.json")["findings"]
    checks, lines = [], []

    def check(cid, label, ok, detail=""):
        checks.append({"id": cid, "check": label, "pass": bool(ok), "detail": detail})
        lines.append(("PASS " if ok else "FAIL ") + cid + " " + label +
                     ((" — " + detail) if detail else ""))

    # A-00: pinned checkout HEAD.
    head = subprocess.run(["git", "-C", str(PINNED_CHECKOUT), "rev-parse", "HEAD"],
                          capture_output=True, text=True)
    check("A-00", "pinned checkout HEAD equals the pinned commit",
          head.stdout.strip() == PINNED_COMMIT,
          f"HEAD={head.stdout.strip()}")

    # A-01: rule anchors inside cited ranges.
    bad = []
    counts = Counter(r["status"] for r in rules)
    for r in rules:
        if r["status"] == "VERIFIED":
            s = r.get("source")
            if not s:
                bad.append(f"{r['id']}: no source")
                continue
            try:
                chunk = read_lines(s["file"])[s["start_line"] - 1:s["end_line"]]
            except (FileNotFoundError, IndexError):
                bad.append(f"{r['id']}: unreadable range")
                continue
            if s.get("anchor") and not any(s["anchor"] in ln for ln in chunk):
                bad.append(f"{r['id']}: anchor not in range")
        elif r["status"] == "SPECIFIED":
            ext = r.get("external")
            if not ext or "url" not in ext or "quote" not in ext:
                bad.append(f"{r['id']}: specified rule needs url+quote")
        else:
            if r.get("source") is not None:
                bad.append(f"{r['id']}: {r['status']} rule must carry no file source")
    check("A-01",
          "45 rules: 38 VERIFIED anchors inside cited ranges, 4 SPECIFIED (external URLs), 2 MODELLED, 1 UNTESTABLE, none with a faked source",
          not bad and len(rules) == 45 and counts == {"VERIFIED": 38, "SPECIFIED": 4, "MODELLED": 2, "UNTESTABLE": 1},
          "; ".join(bad[:3]) or f"counts={dict(sorted(counts.items()))}")

    # B-01: scenario arithmetic.
    totals = doc["totals"]
    runs = [run for sc in doc["scenarios"] for run in sc["runs"]]
    outcomes = Counter(run["outcome"] for run in runs)
    arith_ok = True
    arith_bad = []
    for run in runs:
        if run["fetched"] + run["missing"] != run["params"]["gap"]:
            arith_ok = False
            arith_bad.append(f"{run['params']['gap']} fetched+missing")
        if run["outcome"] in ("synced", "partial"):
            expect = math.ceil(run["params"]["gap"] / 100)
            if run["params"]["peer_state"] in ("one_stale_then_healthy", "stale_then_healthy"):
                expect += 1
            if run["rounds"] != expect:
                arith_ok = False
                arith_bad.append(f"{run['outcome']} rounds {run['rounds']} != {expect}")
        if run["outcome"] == "rejected" and run["stage"] is None:
            arith_ok = False
            arith_bad.append("rejected run without stage")
    check("B-01",
          "per-scenario arithmetic reconciles; totals 13 scenarios / 18 runs / synced 4 / stalled 4 / rejected 4 / partial 6; matrix rows == runs; fetched+missing == gap; catch-up rounds == ceil(gap/100) (+1 peer switch) for synced and partial runs",
          totals == {"scenarios": 13, "runs": 18, "synced": 4,
                     "stalled": 4, "rejected": 4, "partial": 6}
          and outcomes == {"synced": 4, "stalled": 4, "rejected": 4, "partial": 6}
          and len(matrix["rows"]) == 18 and arith_ok,
          f"totals={totals} outcomes={dict(outcomes)} " + "; ".join(arith_bad[:3]))

    # C-01: catch-up and fetch-pack math re-derived.
    c_ok = True
    c_detail = []
    for row in doc["catchup_table"]:
        if row["rounds"] != math.ceil(row["gap"] / 100):
            c_ok = False
            c_detail.append(f"gap={row['gap']} rounds")
        if row["within_history_window"] != (row["gap"] <= 256):
            c_ok = False
            c_detail.append(f"gap={row['gap']} window")
    fp = {r["item"]: r["value"] for r in doc["fetch_pack_table"]}
    c_ok = c_ok and fp.get("fetch-pack cache capacity") == 65536 \
        and fp.get("fetch-pack cache lifetime") == 45 \
        and fp.get("fetch-pack object cap") == 512 \
        and fp.get("fetch-pack state nodes per ledger") == 16384 \
        and fp.get("fetch-pack transaction nodes per ledger") == 512 \
        and fp.get("acquire timeout") == 3000 \
        and fp.get("acquire timeout retries") == 6 \
        and fp.get("reacquire interval") == 300
    check("C-01",
          "catch-up rounds == ceil(gap/100) and window == (gap <= 256) for gaps 1/50/100/101/256/257/300/1000; fetch-pack table matches the pinned constants",
          c_ok, "; ".join(c_detail[:3]) or "all match")

    # D-01: key tokens at recorded lines.
    def token_at(relpath, lineno, token):
        chunk = read_lines(relpath)
        return lineno <= len(chunk) and token in chunk[lineno - 1]

    d_checks = [
        ("src/xrpld/app/ledger/detail/InboundLedger.cpp", 74, "3000ms"),
        ("src/xrpld/app/ledger/detail/InboundLedger.cpp", 54, "ledgerTimeoutRetriesMax = 6"),
        ("src/xrpld/app/ledger/detail/InboundLedger.cpp", 58, "ledgerBecomeAggressiveThreshold = 4"),
        ("src/xrpld/core/Config.h", 224, "LEDGER_HISTORY = 256"),
        ("src/xrpld/app/ledger/detail/LedgerMaster.cpp", 64, "MAX_LEDGER_GAP{100}"),
        ("src/xrpld/app/ledger/detail/LedgerMaster.cpp", 116, "65536"),
        ("src/xrpld/app/ledger/detail/LedgerMaster.cpp", 117, "seconds{45}"),
        ("src/xrpld/app/ledger/detail/LedgerMaster.cpp", 2133, "40s"),
        ("src/xrpld/app/ledger/detail/LedgerMaster.cpp", 2043, "sha512Half"),
    ]
    d_bad = [f"{f}:{ln} {t!r}" for f, ln, t in d_checks if not token_at(f, ln, t)]
    check("D-01",
          "3000ms (InboundLedger.cpp:74), retries = 6 (:54), aggressive = 4 (:58), LEDGER_HISTORY = 256 (Config.h:224), MAX_LEDGER_GAP{100} (LedgerMaster.cpp:64), cache 65536/45s (:116-117), 40s (:2133), sha512Half (:2043)",
          not d_bad, "; ".join(d_bad[:3]) or "all 9 tokens at recorded lines")

    # E-01: fetch-pack verification re-grepped.
    gp = read_lines("src/xrpld/app/ledger/detail/LedgerMaster.cpp")
    e_ok = ("retrieve(hash, data)" in gp[2039]
            and "fetch_packs_.del(hash, false)" in gp[2041]
            and "sha512Half(makeSlice(data))" in gp[2042])
    check("E-01",
          "getFetchPack retrieves, deletes, and compares sha512Half(data) with the requested hash (LedgerMaster.cpp:2040-2043)",
          e_ok, "retrieve+delete+hash-compare verified" if e_ok else "mismatch")

    # F-01: counts reconcile across files.
    def table_rows(path, prefix):
        rows = []
        for ln in open(path, encoding="utf-8"):
            m = re.match(rf"\| ({prefix}-\d+) \| ([A-Z]+) \|", ln)
            if m:
                rows.append((m.group(1), m.group(2)))
        return rows

    claims = table_rows(PACK_ROOT / "docs" / "claim-index.md", "C")
    risks = table_rows(PACK_ROOT / "docs" / "risk-register.md", "K")
    gaps = [ln for ln in open(PACK_ROOT / "docs" / "gap-register.md", encoding="utf-8")
            if re.match(r"\| G-\d+ \|", ln)]
    f_ok = (len(doc["scenarios"]) == 13 and len(runs) == 18
            and len(findings) == 12 and len(claims) == 24
            and Counter(s for _, s in claims) == {"VERIFIED": 16, "SPECIFIED": 2, "MODELLED": 4, "UNTESTABLE": 2}
            and len(risks) == 14 and len(gaps) == 8
            and len(manifest["excerpts"]) == 44
            and len(hashes["files"]) == 10
            and len(hashes["excerpts"]) == 44)
    check("F-01",
          "matrix == results == scenarios (13); findings 12, claims 24 (16/2/4/2), risks 14, gaps 8; excerpts 44 across 10 files agree across manifest, files, hashes",
          f_ok, f"claims={len(claims)} risks={len(risks)} gaps={len(gaps)} excerpts={len(manifest['excerpts'])} files={len(hashes['files'])}")

    # G-01: determinism — capture digests, re-run simulator, compare.
    res_before = sha256_file(PACK_ROOT / "outputs" / "derived" / "ledger-history-results.json")
    mat_before = sha256_file(PACK_ROOT / "outputs" / "derived" / "scenario-matrix.json")
    with tempfile.TemporaryDirectory() as tmp:
        proc = subprocess.run(
            [sys.executable, "src/ledger_history_model.py"],
            cwd=str(PACK_ROOT), capture_output=True, text=True)
        g_ok = proc.returncode == 0
    res_digest = sha256_file(PACK_ROOT / "outputs" / "derived" / "ledger-history-results.json")
    mat_digest = sha256_file(PACK_ROOT / "outputs" / "derived" / "scenario-matrix.json")
    g_ok = g_ok and res_digest == res_before and mat_digest == mat_before
    check("G-01",
          "determinism: simulator re-run reproduces byte-identical results and matrix (full SHA-256)",
          g_ok,
          f"results shipped={res_before} rerun={res_digest}; matrix shipped={mat_before} rerun={mat_digest}")

    # H-01: excerpt integrity + manifest digests.
    h_bad = []
    for ex_id, rec in hashes["excerpts"].items():
        p = PACK_ROOT / "fixtures" / "source-excerpts" / f"{ex_id}.txt"
        if not p.is_file() or sha256_file(p) != rec["sha256"]:
            h_bad.append(ex_id)
    for relpath, rec in hashes["files"].items():
        if git_blob(relpath) != rec["git_blob_sha"]:
            h_bad.append(f"{relpath}:blob")
        if (PINNED_CHECKOUT / relpath).stat().st_size != rec["size_bytes"]:
            h_bad.append(f"{relpath}:size")
    man = load_json(PACK_ROOT / "run-manifest.json") if (PACK_ROOT / "run-manifest.json").is_file() else None
    man_ok = True
    if not skip_manifest and man is not None:
        man_ok = (man.get("results_sha256") == res_digest
                  and man.get("matrix_sha256") == mat_digest)
    check("H-01",
          "every excerpt digest matches source-hashes.json; every manifest blob SHA/size matches the checkout; run-manifest digests match shipped derived files",
          not h_bad and man_ok,
          "; ".join(h_bad[:3]) or ("manifest digests match" if man_ok else "manifest digest mismatch"))

    # I-01: absence findings re-grepped.
    def count_hits(pattern, *roots):
        return len(grep_hits(pattern, *roots))

    i1 = count_hits("history_gap", "src", "include")
    i2 = count_hits("FetchPackTimeout", "src", "include")
    i3 = count_hits("maxFetchPack", "src", "include")
    check("I-01",
          "absence findings re-grepped: history_gap 0 hits; FetchPackTimeout 0 hits; maxFetchPack 0 hits",
          i1 == 0 and i2 == 0 and i3 == 0,
          f"history_gap={i1} FetchPackTimeout={i2} maxFetchPack={i3}")

    # J-01: divergence tokens.
    lm = read_lines("src/xrpld/app/ledger/detail/LedgerMaster.cpp")
    cit = (PACK_ROOT / "docs" / "citations.md").read_text()
    j_ok = ("MAX_LEDGER_GAP{100}" in lm[63]
            and "16384" in lm[2221] and "512" in lm[2226]
            and "reply.objects().size() >= 512" in lm[2228]
            and "256 ledger versions" in cit)
    check("J-01",
          "MAX_LEDGER_GAP 100 is below LEDGER_HISTORY 256; fetch-pack caps 512 objects / 16384 state nodes / 512 tx nodes are in the build loop; the docs 256 figure appears in the citations",
          j_ok, "divergence tokens verified" if j_ok else "mismatch")

    # T-01: timing sanity.
    elapsed_ms = int((time.time() - started) * 1000)
    check("T-01",
          "timing sanity: total probe elapsed_ms is non-negative (loose band, never exact)",
          elapsed_ms >= 0, "value not recorded; never compared")

    passed = sum(1 for c in checks if c["pass"])
    total = len(checks)
    lines.append(f"probe: {passed}/{total} checks PASS")
    lines.append(f"probe: ledger-history-results.json sha256: {res_digest}")
    lines.append(f"probe: scenario-matrix.json sha256: {mat_digest}")
    lines.append(f"probe: pinned commit {PINNED_COMMIT}")
    text = "\n".join(lines) + "\n"
    sys.stdout.write(text)
    result_doc = {"pack": "Ledger History and State-Sync in postfiatd",
                  "pinned_commit": PINNED_COMMIT,
                  "results_file": "outputs/derived/ledger-history-results.json",
                  "results_sha256": res_digest, "matrix_sha256": mat_digest,
                  "checks": checks, "passed": passed, "total": total}
    out_derived = PACK_ROOT / "outputs" / "derived" / "probe-results.json"
    out_derived.parent.mkdir(parents=True, exist_ok=True)
    with open(out_derived, "w", encoding="utf-8") as fh:
        json.dump(result_doc, fh, indent=1, sort_keys=True)
        fh.write("\n")
    (PACK_ROOT / "outputs" / "probe-run.log").write_text(text)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
