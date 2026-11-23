# Risk register

Poisoning, eclipse, liveness, and storage-exhaustion risks in
ledger history fetching and state sync. Severity is judged by
impact on the node's ability to stay in sync and to serve correct
history.

| Risk | Severity | Risk | Evidence / mitigation in the pinned code |
| --- | --- | --- | --- |
| K-01 | HIGH | Poisoned fetch pack: a peer serves a header whose hash matches the request but whose state or transaction nodes are tampered. | Header hash is the identity (R-05); state/tx nodes are hash-checked against the roots when the SHAMap is fetched (R-35, R-44). A fully consistent tampered ledger still needs a colliding hash. |
| K-02 | HIGH | Eclipse by stale peers: every connected peer reports a validated age over 40 seconds, so no fetch pack is ever built. | Fetch-pack builds are refused above 40 s (R-13); the node then has no history source until a fresh peer connects. |
| K-03 | HIGH | History gap beyond the window: a node offline longer than 256 ledgers cannot backfill from peers at all. | shouldAcquire refuses out-of-window ledgers (R-20); the only recovery is a full-history source or a fresh sync. |
| K-04 | MEDIUM | Timeout storm: repeated 3-second timeouts on a slow peer consume the 6-retry budget, then the 5-minute reacquire block delays a single ledger. | R-02, R-08; the aggressive mode after 4 timeouts (R-03) asks peers directly by hash. |
| K-05 | MEDIUM | Fetch-pack load concentration: busy or behind nodes refuse to serve, so the few in-sync peers carry all history requests. | R-13; there is no load balancing beyond the latency-biased peer score (R-16). |
| K-06 | MEDIUM | Partial-history peer: a peer advertises a range it only partly holds; the node fetches what it can and stalls on the rest. | Scenario S-08; `haveLedger` / `getLedgerHashForHistory` resolve hashes only for ledgers the chain actually holds. |
| K-07 | MEDIUM | Parent-hash mismatch on accept: a fetched ledger whose parent does not match the held previous ledger invalidates prior ledgers backwards. | R-26, `fixMismatch` walks backwards clearing ledgers until the chain closes. |
| K-08 | MEDIUM | Stale cached fetch packs: a 45-second cache can hand out nodes for a ledger the network has since moved past. | R-10, R-11; entries are consumed on read and hash-checked, so staleness is bounded by the hash check, not by the clock. |
| K-09 | MEDIUM | SHAMap sync amplification: a large state map needs many 256-node passes, each a separate peer round trip. | R-33, R-35; the random first-child start spreads the load across threads. |
| K-10 | MEDIUM | Storage exhaustion: without online deletion, retained history grows without bound; the fetch-pack cache alone holds 65536 entries. | R-10; `online_delete` bounds retention (R-42), but it is a deployment setting, not a code guarantee. |
| K-11 | MEDIUM | LedgerCleaner contention: the cleaner sleeps 2 seconds on failure and 100 ms on success, sharing I/O with the fetcher. | E42: `LedgerCleaner.cpp:382-410`; the cleaner waits for acquiring to catch up. |
| K-12 | LOW | Stale-data stash: nodes received for a finished acquire are kept and may be served later without a fresh hash check at stash time. | R-17; the hash check happens on use (R-11), not at stash time. |
| K-13 | LOW | Replay misuse: the experimental replay path is off by default, so an operator enabling it inherits its 500 ms task timeouts and 10-task cap. | R-37, R-38. |
| K-14 | LOW | Short mismatch-analysis window: the consensus-validated cache holds 64 entries for 5 minutes, so a slow mismatch investigation loses its inputs. | R-32. |
