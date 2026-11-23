# Operator decision memo

## Untrustworthy history

A fetched ledger is trusted only when its hashes check out:

1. **Header first.** The header's hash must equal the requested hash
   and its sequence must equal the requested sequence; anything else
   fails the acquire outright and the ledger "can never be acquired"
   (R-05). Do not retry a mismatched header against the same peer —
   the data is wrong, not slow.
2. **Roots, then nodes.** State is fetched before transactions
   (R-36, E36 and the comment at `InboundLedger.cpp:619`), and each
   SHAMap node is checked against the root hash as it arrives. A
   single bad node fails the whole acquire (scenarios S-05, S-06).
3. **Zero account hash is fatal.** A header with a zero account hash
   fails in `tryDB` (R-06, scenario S-11). Treat it as corrupt data,
   not as an empty ledger.
4. **Parent check on accept.** When a fetched ledger is accepted,
   its parent hash is compared with the held previous ledger; a
   mismatch invalidates prior ledgers backwards until the chain
   closes (R-26). If the node starts invalidating a long run of
   ledgers, stop and inspect the peer that served them — the chain,
   not one ledger, is suspect.
5. **No signature exists.** Fetch-pack integrity rests on hash
   equality alone (R-11, F-03). The defence is the hash check, not
   the peer: never accept ledger data that bypasses it.

## Failed catch-up

When the node is behind and not catching up, check in this order:

1. **Are we in sync at all?** History backfill runs only while the
   node is in sync: validated age under 1 minute, valid == published,
   write load under 8192, fewer than 10 `jtPUBOLDLEDGER` jobs (R-18).
   A behind node never backfills — fix current sync first.
2. **Is the gap inside the window?** More than 256 ledgers behind
   means the gap is not acquired from peers (R-20). The recovery is
   a full-history source or a fresh sync, not more retries (F-01).
3. **Is any peer fresh?** Peers with a validated age over 40 seconds
   refuse to build fetch packs (R-13). If every peer is stale, the
   node has no history source until a fresh peer connects (K-02).
4. **Did we hit the retry limit?** Seven timeouts fail the acquire
   and block reacquisition for 5 minutes (R-02, R-08). Wait out the
   block; retrying sooner is refused by `isFailure`.
5. **Is the gap below the earliest ledger?** Nothing below
   `earliestLedgerSeq` is fetched (R-25, scenario S-13). The floor
   moves only when the node store advances.

## Most change-sensitive sync parameters

| Parameter | Pinned value | What changes if you move it |
| --- | --- | --- |
| `LEDGER_HISTORY` | 256 | Larger: a node can backfill deeper gaps after downtime, at the cost of more retained history. Smaller: shorter recovery window. |
| `MAX_LEDGER_GAP` | 100 | Larger: fewer `doAdvance` rounds per gap, more work per round. Smaller: slower catch-up. |
| Fetch-pack caps (512 objects, 16384 state / 512 tx nodes, 1 s) | hard-coded | Raising the caps means fewer round trips for deep gaps but larger single replies and longer build times. |
| Fetch-pack refusal age (40 s) | hard-coded | Raising it lets stale nodes serve history; lowering it concentrates load on the freshest peers. |
| Validated-age gate for backfill (1 min) | hard-coded | Raising it lets a slightly-behind node backfill sooner; lowering it delays all backfill. |
| Acquire timeout (3000 ms) / retries (6) / reacquire block (5 min) | hard-coded | Shorter timeouts fail slow peers faster; a longer block delays recovery after a failure. |
| `FETCH_DEPTH` | 1,000,000,000 | Bounds how far back a peer will serve; with `online_delete` it is silently clamped (R-42). |

All of the above except `LEDGER_HISTORY` and `FETCH_DEPTH` are
hard-coded constants in the pinned commit — changing them means
changing the source and rebuilding, not editing configuration.
