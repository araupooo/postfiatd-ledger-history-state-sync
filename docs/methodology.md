# Methodology

## Pinned source

All source findings are pinned to postfiatd commit
`0085a1ff885d6a446369cf73a4430f75af22be55` (2026-10-10). Every cited
line was verified with `grep -n` on a local checkout of that commit
(`~/workspace/postfiatd-pin-0085a1f`); no line number comes from a web
fetch. The 44 verbatim excerpts in `fixtures/source-excerpts/` were
extracted by `scripts/extract_excerpts.py` from that checkout, and
`fixtures/source-hashes.json` records the SHA-256, git blob SHA, and
size of every excerpt and every cited source file.

## How the rules were built

1. Read the ledger-fetching code paths end to end: `InboundLedgers`
   (acquire, reacquire block, stale-data stash), `InboundLedger`
   (timeout machine, header/state/transaction stages, aggressive
   mode), `LedgerMaster` (fetch-pack build/serve, `doAdvance` sync
   gates, `shouldAcquire`, `fetchForHistory`, `tryFill`,
   `setFullLedger` parent check), `LedgerHistory` (insert, lookup,
   mismatch classification), SHAMap sync (`getMissingNodes`, the
   `AccountStateSF` / `TransactionStateSF` fetch-pack fallbacks), and
   the replay path (`LedgerReplayer`, `LedgerReplayTask` limits).
2. Recorded every hard-coded constant that bounds the behaviour:
   3000 ms timeout, 6 retries, 4-timeout aggression, 5/3 peers,
   256/128/12 node counts, 65536-entry 45-second fetch-pack cache,
   512-object / 16384-state / 512-tx fetch-pack caps, 1-second build
   budget, 40-second refusal age, 100-ledger catch-up cap, 256-ledger
   history window, 1-minute validated-age gate, 8192 write-load gate,
   3-minute / 90-second caught-up bounds, 5-minute reacquire block,
   replay limits (10 tasks, 256 ledgers, 500 ms).
3. Cross-checked the public documentation against the code and
   recorded the four SPECIFIED rules with verbatim quotes in
   `docs/citations.md`. Where docs and code disagree, the pack follows
   the code and says so (see `docs/citations.md`, divergence notes).
4. Absence findings (no `history_gap`, `FetchPackTimeout`, or
   `maxFetchPack` symbol anywhere in `src/` or `include/`) were
   re-grepped by the probe (I-01).

## How the simulator works

`src/ledger_history_model.py` reads `configs/scenarios.json` and
applies the pinned rules to 13 scenarios / 18 runs. A gap of G
ledgers closes in ceil(G / 100) `doAdvance` rounds (MAX_LEDGER_GAP);
a run is rejected when a hash check fails, partial when the gap lies
outside the 256-ledger window or a peer serves only part of it, and
stalled when no peer can serve the data, all peers are stale, or the
acquire fails the timeout limit. The only time figures are the pinned
constants (3000 ms timeout, 300 s reacquire block). No live node was
run; nothing in the simulator is presented as a code fact.

## Reproduction

```bash
bash scripts/run_all.sh        # exit 0 only if every check passes
bash scripts/clean_reproduce.sh  # fresh-copy reproduction (run twice)
```

`run_all.sh` re-extracts the excerpts from the pinned checkout,
validates the configs, runs the simulator, runs the 12-check probe
twice (the second run verifies the run-manifest digests), writes the
run manifest, and lists full 64-character SHA-256 digests of every
deterministic output in `outputs/run.log`. `clean_reproduce.sh`
copies the pack to a throwaway directory, drops all generated
outputs, re-runs everything from scratch, and compares the fresh
results with the shipped ones; the comparison is recorded in
`outputs/fresh-clone-compare.log` and the fresh outputs in
`outputs/fresh-clone-*`.

## What is simulated vs source-derived

- **Source-derived:** all 38 VERIFIED rules, the 44 excerpts, every
  constant in the fetch-pack and catch-up tables.
- **Simulated:** the 13 scenarios / 18 runs and the catch-up table —
  deterministic outputs of `src/ledger_history_model.py` on the
  stated inputs in `configs/scenarios.json`. Simulated results are
  labelled MODELLED in the claim index and are never presented as
  code facts.
- **Unknown:** live-network state (real peer behaviour, live
  `minimumOnline`, real close cadence, the `ledger_fetch_size_`
  value for each node size) — see `docs/gap-register.md`. No live
  node was run.
