# Claim-to-evidence index

Every claim in this pack, its status, and the exact evidence for it.
Status meanings: VERIFIED — read from the pinned source with a
grep-verified file:line citation; SPECIFIED — stated in the cited public
documentation and cross-checked against code; MODELLED — an output of
the deterministic simulator on the stated inputs; UNTESTABLE — not
decidable from the pinned source alone.

| Claim | Status | Claim | Evidence |
| --- | --- | --- | --- |
| C-01 | VERIFIED | One ledger acquire times out after 3000 ms. | R-01, E01: `src/xrpld/app/ledger/detail/InboundLedger.cpp:74`. |
| C-02 | VERIFIED | More than 6 timeouts fails the acquire; after 4 timeouts it goes aggressive and indirect. | R-02, R-03, E02, E03: `InboundLedger.cpp:52-58, 376-389, 531-540`. |
| C-03 | VERIFIED | A header whose hash or sequence mismatches the request can never be acquired. | R-05, E05: `InboundLedger.cpp:246-262`. |
| C-04 | VERIFIED | A fetch-pack entry is verified by sha512Half and consumed on read. | R-11, E11: `src/xrpld/app/ledger/detail/LedgerMaster.cpp:2036-2048`. |
| C-05 | VERIFIED | A fetch pack holds at most 512 objects, 16384 state nodes and 512 transaction nodes per ledger, built within 1 second. | R-14, E14: `LedgerMaster.cpp:2218-2235`. |
| C-06 | VERIFIED | History backfill runs only while the node is in sync (validated age under 1 minute, valid == published, write load under 8192). | R-18, E18: `LedgerMaster.cpp:1946-1956`. |
| C-07 | VERIFIED | Catch-up is capped at a 100-ledger gap per step. | R-19, E19: `LedgerMaster.cpp:62-66`. |
| C-08 | VERIFIED | A missing ledger is acquired only if current, within the 256-ledger history window, or at/after minimumOnline. | R-20, R-21, E20, E21: `LedgerMaster.cpp:75-103`, `Config.h:222-226`. |
| C-09 | VERIFIED | Caught-up means a fresh published ledger and a validated ledger within 90 seconds of it. | R-22, E22: `LedgerMaster.cpp:217-239`. |
| C-10 | VERIFIED | Accepting a ledger re-checks its parent; a mismatch invalidates prior ledgers until the chain closes. | R-26, E26: `LedgerMaster.cpp:870-888`. |
| C-11 | VERIFIED | LedgerHistory accepts only immutable ledgers with a nonzero state hash, and getLedgerByHash asserts the hash matches. | R-27, R-29, E27, E29: `src/xrpld/app/ledger/LedgerHistory.cpp:55-67, 123-158`. |
| C-12 | VERIFIED | Built-then-validated hash disagreements trigger mismatch classification (parent, close time, consensus set). | R-30, R-31, E30, E31: `LedgerHistory.cpp:377-401, 493-535`. |
| C-13 | VERIFIED | SHAMap sync asks for at most 256 missing nodes per pass and falls back to the fetch-pack cache. | R-33, R-34, E33, E34: `src/xrpld/shamap/detail/SHAMapSync.cpp:319-332`, `AccountStateSF.cpp:25-40`. |
| C-14 | VERIFIED | A failed acquire blocks reacquisition for 5 minutes. | R-08, E08: `src/xrpld/app/ledger/detail/InboundLedgers.cpp:48-52`. |
| C-15 | VERIFIED | A loaded node, or one whose validated ledger is older than 40 seconds, refuses to build a fetch pack. | R-13, E13: `LedgerMaster.cpp:2132-2138`. |
| C-16 | VERIFIED | Ledger replay is disabled by default and bounded (10 tasks, 256 ledgers each, 500 ms timeouts). | R-37, R-38, E37, E38: `Config.h:237-240`, `LedgerReplayer.h:39-67`. |
| C-17 | SPECIFIED | A server needs only the most recent 256 ledgers to follow consensus. | R-39, `docs/citations.md` S-01: capacity-planning documentation, 24 Nov 2026. |
| C-18 | SPECIFIED | Ledger data arrives in the order header hash, header, roots, state nodes, transaction nodes; backfill runs only when caught up, local store first, then peers. | R-40, R-41, `docs/citations.md` S-02, S-03: ledger directory reference, 24 Nov 2026. |
| C-19 | MODELLED | A gap of G ledgers needs ceil(G / 100) advance rounds when peers cooperate. | R-43; `outputs/derived/ledger-history-results.json` catchup_table; scenarios S-01, S-02, S-03. |
| C-20 | MODELLED | A tampered fetch-pack node is detected at the hash check, not at receipt. | R-44; scenarios S-05, S-06, S-11 (all rejected). |
| C-21 | MODELLED | A gap beyond the 256-ledger window leaves the out-of-window ledgers unfetched (partial). | Scenarios S-04 (257: 256 fetched, 1 missing); S-08 (partial-history peers). |
| C-22 | MODELLED | Seven timeouts fail the acquire; reacquisition after the 300-second block succeeds on healthy peers. | Scenarios S-09 run A (stalled) and run B (synced). |
| C-23 | UNTESTABLE | Whether real peers serve fetch packs on demand, and how an eclipse or poisoning attempt plays out live. | R-45; `docs/gap-register.md` G-01, G-02. |
| C-24 | UNTESTABLE | The real close cadence and the live value of ledger_fetch_size_ by node size. | `docs/gap-register.md` G-03, G-05. |
