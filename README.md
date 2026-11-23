# Ledger History and State-Sync in postfiatd

How postfiatd fetches, verifies, and replays ledger history, catches
up from behind, handles history gaps, and rejects corrupt or stale
history — at commit `0085a1ff885d6a446369cf73a4430f75af22be55`
(2026-10-10).

## Headline findings

- **A node more than 256 ledgers behind cannot backfill from peers.**
  `shouldAcquire` refuses out-of-window ledgers
  (`LedgerMaster.cpp:75-103`); recovery needs a full-history source
  or a fresh sync.
- **Backfill never runs while the node is behind.** History fetch
  requires validated age under 1 minute, valid == published, and
  write load under 8192 (`LedgerMaster.cpp:1948-1955`).
- **Catch-up is capped at 100 ledgers per step** (`MAX_LEDGER_GAP`),
  so a 1000-ledger gap needs at least 10 `doAdvance` rounds.
- **Fetch-pack integrity rests on hash equality alone.** Entries are
  verified with `sha512Half` and consumed on read
  (`LedgerMaster.cpp:2036-2048`); packs carry no signature.
- **A fetch pack holds at most 512 objects**, 16384 state nodes and
  512 transaction nodes per ledger, built within 1 second — and a
  node whose validated ledger is older than 40 seconds refuses to
  build one at all.

## Contents

- 45 rules (VERIFIED 38, SPECIFIED 4, MODELLED 2, UNTESTABLE 1) —
  `configs/ledger-history-rules.json`, with grep-verified file:line
  ranges and verbatim excerpts in `fixtures/source-excerpts/` (44
  excerpts, 10 source files).
- Deterministic simulator (`src/ledger_history_model.py`) + scenario
  matrix — 13 scenarios, 18 runs: synced 4, stalled 4, rejected 4,
  partial 6.
- Claim-to-evidence index: 24 claims (VERIFIED 16, SPECIFIED 2,
  MODELLED 4, UNTESTABLE 2) — `docs/claim-index.md`.
- Findings: 12 (HIGH 3, MEDIUM 5, LOW 4) — `findings.json`.
- Risk register: 14 risks (HIGH 3, MEDIUM 8, LOW 3) —
  `docs/risk-register.md`. Gap register: 8 gaps —
  `docs/gap-register.md`.
- Operator decision memo (untrustworthy history, failed catch-up,
  most change-sensitive sync parameters) — `docs/decision-memo.md`.
  Methodology — `docs/methodology.md`. Evidence index —
  `docs/evidence-index.md`.

## Reproduction

```bash
bash scripts/run_all.sh        # exit 0 only if every check passes
bash scripts/clean_reproduce.sh  # fresh-copy reproduction (run twice)
```

- Full suite: `run_all.sh` exits 0; probe 12/12 checks pass.
- `outputs/run.log` (unedited full-run log, 10 lines) SHA-256:
  `71d1b52fe51eb6d80f95ec4d36446f270f22b2944783149b04ac4f0cae43bf18`
- Fresh-copy reproduction was run twice; both passed with
  byte-identical deterministic outputs. Fresh-clone run log:
  `outputs/fresh-clone-run.log` SHA-256:
  `71d1b52fe51eb6d80f95ec4d36446f270f22b2944783149b04ac4f0cae43bf18`
  (identical to the shipped `run.log` digest — the fresh copy
  reproduces the shipped log byte-for-byte).
- Digests: `ledger-history-results.json`
  `7fa88de8cd91d7b403c2b8bda3eeab50de330b6674a65a13eaf055b609c9c1f7`;
  `scenario-matrix.json`
  `1a2077882b89c20fe8cc3bc8e2f38b8d1a7e3ecb4ace4ec656c02836cb978f4d`.
- Verify all digests: `bash scripts/verify_digests.sh`.

## CI

Continuous integration runs the same suite on every push; see the
workflow runs page:

https://github.com/araupooo/postfiatd-ledger-history-state-sync/actions/workflows/verify.yml

## What is simulated vs source-derived

- **Source-derived:** all 38 VERIFIED rules, the 44 excerpts, the
  fetch-pack and catch-up constants.
- **Simulated:** the 13 scenarios / 18 runs and the catch-up table —
  deterministic outputs of `src/ledger_history_model.py` on the stated
  inputs in `configs/scenarios.json`. Simulated results are labelled
  MODELLED in the claim index and are never presented as code facts.
- **Unknown:** live-network state (real peer behaviour, live
  `minimumOnline`, real close cadence, the `ledger_fetch_size_`
  value for each node size) — see `docs/gap-register.md`. No live
  node was run.
