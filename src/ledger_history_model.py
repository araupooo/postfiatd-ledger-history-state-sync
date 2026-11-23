#!/usr/bin/env python3
"""ledger_history_model.py — deterministic ledger-history / state-sync model.

Usage:
    python3 src/ledger_history_model.py [--help]

Reads configs/scenarios.json and writes:
    outputs/derived/ledger-history-results.json
    outputs/derived/scenario-matrix.json

Every number comes from the scenario inputs plus the pinned-code
constants in configs/scenarios.json (LEDGER_HISTORY 256, MAX_LEDGER_GAP
100, acquire timeout 3000 ms, 6 timeout retries, 5-minute reacquire
block, fetch-pack caps 512 objects / 16384 state nodes / 512 tx nodes,
fetch-pack refusal when validated age exceeds 40 s). No live node is
involved, no timestamps are recorded, and no wall-clock time is
measured: re-running produces byte-identical outputs.

Outcome rules (each is a direct application of a pinned rule):
  - tampered header / state node / transaction node / zero account hash
    -> rejected at the stage whose hash check fails.
  - no peer holds the ledger -> stalled.
  - gap reaching below earliestLedgerSeq -> stalled; only the ledgers
    at or above the earliest sequence are fetchable.
  - more than 6 timeouts before progress -> stalled; the acquire
    fails and the 300 s reacquire block applies.
  - all peers stale (validated age over 40 s) -> stalled; fetch-pack
    builds are refused.
  - otherwise the node catches up to the live tip in ceil(gap / 100)
    doAdvance rounds (MAX_LEDGER_GAP also bounds the publish path),
    plus one round when a stale peer has to be replaced by a healthy
    one; history backfill then fetches at most the 256 in-window
    ledgers (fewer when the best peer serves less):
      synced  = tip reached AND the whole gap backfilled;
      partial = tip reached BUT part of the gap stays unfetched.
"""
import json
import math
import sys
from pathlib import Path

PACK_ROOT = Path(__file__).resolve().parent.parent
PINNED_COMMIT = "0085a1ff885d6a446369cf73a4430f75af22be55"
MODEL_CURRENT_SEQ = 1000  # model parameter: the node's current ledger in S-13


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def simulate_run(scenario, run, consts):
    p = run["params"]
    gap = p["gap"]
    peers = p["peers"]
    peer_state = p["peer_state"]
    tamper = p["tamper"]
    timeouts = p["timeouts_before_progress"]
    earliest = p.get("earliest_seq")
    peer_have = p.get("peer_have")
    minimum_online = p.get("minimum_online")
    lh = consts["ledger_history"]
    max_gap = consts["max_ledger_gap"]
    max_timeouts = consts["timeout_retries_max"]

    events = [{"round": ev["round"], "text": ev["text"]}
              for ev in run["events"]]
    outcome = None
    reason = None
    stage = None
    fetched = 0
    missing = gap
    rounds = 0
    reacquire_wait_s = 0

    if tamper == "header":
        outcome, reason, stage = ("rejected", "header_hash_mismatch", "header")
        events.append({"round": 0, "text": "header hash != requested hash: acquire failed, ledger can never be acquired"})
    elif tamper == "state_node":
        outcome, reason, stage = ("rejected", "state_node_hash_mismatch", "state")
        events.append({"round": 0, "text": "state node bytes do not hash to the advertised node hash: acquire failed"})
    elif tamper == "tx_node":
        outcome, reason, stage = ("rejected", "tx_node_hash_mismatch", "transactions")
        events.append({"round": 0, "text": "transaction node bytes do not hash to the advertised node hash: acquire failed"})
    elif tamper == "zero_account_hash":
        outcome, reason, stage = ("rejected", "zero_account_hash", "state")
        events.append({"round": 0, "text": "header carries a zero account hash: acquire failed in tryDB"})
    elif peer_state == "none" or peers == 0:
        outcome, reason = "stalled", "no_peer_holds_ledger"
        events.append({"round": 0, "text": "no active peer has the ledger range: no fetch pack requested"})
    elif earliest is not None:
        first_needed = MODEL_CURRENT_SEQ - gap + 1
        below = max(0, earliest - first_needed)
        fetchable = gap - below
        outcome, reason = "stalled", "gap_below_earliest_ledger_seq"
        fetched, missing = fetchable, below
        events.append({"round": 0, "text": f"fetch stops at earliestLedgerSeq {earliest}: {below} ledgers below it cannot be fetched"})
    elif peer_state == "partial":
        outcome, reason = "partial", "peer_serves_partial_history"
        fetched, missing = min(peer_have, lh), gap - min(peer_have, lh)
        rounds = math.ceil(gap / max_gap)
        if peer_state in ("one_stale_then_healthy", "stale_then_healthy"):
            rounds += 1
        remaining = gap
        for k in range(1, rounds + 1):
            take = min(max_gap, remaining)
            events.append({"round": k, "text": f"round {k}: caught up {take} ledgers toward the live tip"})
            remaining -= take
        events.append({"round": rounds, "text": f"tip reached; history backfill fetched {fetched} of {gap} ledgers; {missing} remain unserved by the peer"})
    elif gap > lh and minimum_online is None:
        outcome, reason = "partial", "gap_beyond_history_window"
        fetched, missing = lh, gap - lh
        rounds = math.ceil(gap / max_gap)
        if peer_state in ("one_stale_then_healthy", "stale_then_healthy"):
            rounds += 1
            events.append({"round": 0, "text": "stale peer replaced by a healthy peer: one extra round"})
        remaining = gap
        for k in range(1, rounds + 1):
            take = min(max_gap, remaining)
            events.append({"round": k, "text": f"round {k}: caught up {take} ledgers toward the live tip"})
            remaining -= take
        events.append({"round": rounds, "text": f"tip reached; history backfill fetched {fetched} of {gap} ledgers; {missing} outside the {lh}-ledger window remain unfetched"})
    elif timeouts > max_timeouts:
        outcome, reason = "stalled", "acquire_failed_after_timeout_limit"
        reacquire_wait_s = consts["reacquire_interval_s"]
        events.append({"round": 0, "text": f"{timeouts} timeouts exceed the {max_timeouts} retry limit: acquire failed, reacquire blocked for {reacquire_wait_s} s"})
    elif peer_state == "all_stale":
        outcome, reason = "stalled", "fetch_pack_refused_validated_age_over_40s"
        events.append({"round": 0, "text": "every peer reports validated age over 40 s: fetch-pack build refused"})
    else:
        outcome, reason = "synced", "acquired_via_fetch_pack_and_shamap_sync"
        rounds = math.ceil(gap / max_gap)
        if peer_state in ("one_stale_then_healthy", "stale_then_healthy"):
            rounds += 1
            events.append({"round": 0, "text": "stale peer replaced by a healthy peer: one extra round"})
        fetched, missing = gap, 0
        remaining = gap
        for k in range(1, rounds + 1):
            take = min(max_gap, remaining)
            events.append({"round": k, "text": f"round {k}: acquired {take} ledgers via fetch pack + SHAMap sync"})
            remaining -= take

    return {
        "label": run["label"],
        "title": run["title"],
        "params": p,
        "outcome": outcome,
        "reason": reason,
        "stage": stage,
        "fetched": fetched,
        "missing": missing,
        "rounds": rounds,
        "timeouts": timeouts,
        "reacquire_wait_s": reacquire_wait_s,
        "events": events,
    }


def main():
    if "--help" in sys.argv[1:]:
        print(__doc__.strip())
        print("\nusage: python3 src/ledger_history_model.py [--help]")
        return 0
    sc = load_json(PACK_ROOT / "configs" / "scenarios.json")
    consts = sc["constants"]
    assert sc.get("pinned_commit") == PINNED_COMMIT, "scenarios pinned_commit mismatch"
    assert sc.get("schema_version") == 1, "scenarios schema_version != 1"

    results_scenarios = []
    matrix_rows = []
    totals = {"scenarios": 0, "runs": 0, "synced": 0, "stalled": 0,
              "rejected": 0, "partial": 0}
    for scenario in sc["scenarios"]:
        runs = [simulate_run(scenario, run, consts)
                for run in scenario["runs"]]
        results_scenarios.append({
            "id": scenario["id"],
            "title": scenario["title"],
            "runs": runs,
        })
        totals["scenarios"] += 1
        for run in runs:
            totals["runs"] += 1
            totals[run["outcome"]] += 1
            matrix_rows.append({
                "scenario": scenario["id"],
                "run": run["label"],
                "gap": run["params"]["gap"],
                "outcome": run["outcome"],
                "reason": run["reason"],
                "fetched": run["fetched"],
                "missing": run["missing"],
                "rounds": run["rounds"],
                "timeouts": run["timeouts"],
            })

    catchup_table = [
        {"gap": g, "rounds": math.ceil(g / consts["max_ledger_gap"]),
         "within_history_window": g <= consts["ledger_history"]}
        for g in (1, 50, 100, 101, 256, 257, 300, 1000)
    ]
    fetch_pack_table = [
        {"item": "fetch-pack cache capacity", "value": consts["fetch_pack_cache_entries"], "unit": "entries"},
        {"item": "fetch-pack cache lifetime", "value": consts["fetch_pack_ttl_s"], "unit": "s"},
        {"item": "fetch-pack object cap", "value": consts["fetch_pack_max_objects"], "unit": "objects"},
        {"item": "fetch-pack state nodes per ledger", "value": consts["fetch_pack_state_nodes"], "unit": "nodes"},
        {"item": "fetch-pack transaction nodes per ledger", "value": consts["fetch_pack_tx_nodes"], "unit": "nodes"},
        {"item": "fetch-pack request staleness", "value": 1, "unit": "s"},
        {"item": "fetch-pack refusal validated age", "value": consts["fetch_pack_refuse_validated_age_s"], "unit": "s"},
        {"item": "acquire timeout", "value": consts["acquire_timeout_ms"], "unit": "ms"},
        {"item": "acquire timeout retries", "value": consts["timeout_retries_max"], "unit": "timeouts"},
        {"item": "reacquire interval", "value": consts["reacquire_interval_s"], "unit": "s"},
    ]

    results = {
        "pack": "Ledger History and State-Sync in postfiatd",
        "pinned_commit": PINNED_COMMIT,
        "model_current_seq": MODEL_CURRENT_SEQ,
        "constants": consts,
        "scenarios": results_scenarios,
        "totals": totals,
        "catchup_table": catchup_table,
        "fetch_pack_table": fetch_pack_table,
    }
    matrix = {"rows": matrix_rows, "totals": totals}

    outdir = PACK_ROOT / "outputs" / "derived"
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / "ledger-history-results.json", "w") as fh:
        json.dump(results, fh, indent=1, sort_keys=True)
        fh.write("\n")
    with open(outdir / "scenario-matrix.json", "w") as fh:
        json.dump(matrix, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print(f"simulator: {totals['scenarios']} scenarios, {totals['runs']} runs")
    print(f"simulator: synced {totals['synced']}, stalled {totals['stalled']}, "
          f"rejected {totals['rejected']}, partial {totals['partial']}")
    print("simulator: wrote outputs/derived/ledger-history-results.json")
    print("simulator: wrote outputs/derived/scenario-matrix.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
