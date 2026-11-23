# Scenario matrix

Deterministic outputs of `src/ledger_history_model.py` on
`configs/scenarios.json`. Rounds are `ceil(gap / 100)` (MAX_LEDGER_GAP),
plus one round when a stale peer is replaced by a healthy one.
`fetched + missing == gap` for every run.

| Scenario | Run | Gap | Outcome | Reason | Fetched | Missing | Rounds | Timeouts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S-01 | A | 300 | partial | gap_beyond_history_window | 256 | 44 | 3 | 0 |
| S-02 | A | 1000 | partial | gap_beyond_history_window | 256 | 744 | 10 | 0 |
| S-02 | B | 1000 | partial | gap_beyond_history_window | 256 | 744 | 11 | 1 |
| S-03 | A | 256 | synced | acquired_via_fetch_pack_and_shamap_sync | 256 | 0 | 3 | 0 |
| S-04 | A | 257 | partial | gap_beyond_history_window | 256 | 1 | 3 | 0 |
| S-05 | A | 20 | rejected | header_hash_mismatch | 0 | 20 | 0 | 0 |
| S-05 | B | 20 | rejected | tx_node_hash_mismatch | 0 | 20 | 0 | 0 |
| S-06 | A | 40 | rejected | state_node_hash_mismatch | 0 | 40 | 0 | 0 |
| S-07 | A | 120 | stalled | fetch_pack_refused_validated_age_over_40s | 0 | 120 | 0 | 0 |
| S-07 | B | 120 | synced | acquired_via_fetch_pack_and_shamap_sync | 120 | 0 | 3 | 2 |
| S-08 | A | 300 | partial | peer_serves_partial_history | 100 | 200 | 3 | 0 |
| S-08 | B | 300 | partial | peer_serves_partial_history | 50 | 250 | 3 | 0 |
| S-09 | A | 50 | stalled | acquire_failed_after_timeout_limit | 0 | 50 | 0 | 7 |
| S-09 | B | 50 | synced | acquired_via_fetch_pack_and_shamap_sync | 50 | 0 | 1 | 0 |
| S-10 | A | 80 | stalled | no_peer_holds_ledger | 0 | 80 | 0 | 0 |
| S-11 | A | 10 | rejected | zero_account_hash | 0 | 10 | 0 | 0 |
| S-12 | A | 1 | synced | acquired_via_fetch_pack_and_shamap_sync | 1 | 0 | 1 | 0 |
| S-13 | A | 150 | stalled | gap_below_earliest_ledger_seq | 101 | 49 | 0 | 0 |

Totals: 13 scenarios, 18 runs — synced 4, stalled 4, rejected 4,
partial 6.

## Catch-up table

| Gap | Rounds (ceil(gap / 100)) | Within the 256-ledger window |
| --- | --- | --- |
| 1 | 1 | yes |
| 50 | 1 | yes |
| 100 | 1 | yes |
| 101 | 2 | yes |
| 256 | 3 | yes |
| 257 | 3 | no |
| 300 | 3 | no |
| 1000 | 10 | no |

## Reading the outcomes

- **Synced** runs reach the live tip and backfill the whole gap
  through fetch packs and SHAMap sync (S-03, S-07 B, S-09 B, S-12).
  A stale peer that has to be replaced adds one round (S-07 B).
- **Partial** runs reach the live tip but leave part of the gap
  unfetched: the 300- and 1000-ledger gaps exceed the 256-ledger
  window (S-01, S-02, S-04), or the best peer holds only 100 / 50
  of 300 ledgers (S-08). The 1000-ledger gap still needs 10 rounds
  to reach the tip; a stale peer adds one more (S-02 B).
- **Rejected** runs fail a hash check: header (S-05 A), transaction
  node (S-05 B), state node (S-06), zero account hash (S-11).
  Rejection is immediate and permanent for that data.
- **Stalled** runs cannot proceed at all: no peer holds the ledger
  (S-10), every peer is stale (S-07 A), the acquire exceeded the
  retry limit (S-09 A), or the gap reaches below the earliest
  ledger (S-13, 101 of 150 fetchable, 49 below the floor).
