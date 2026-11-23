# Gap register

Questions the pinned source alone cannot answer. Each gap is a
source-only limitation: it names what is unknown, why it is unknown,
and what would close it.

| Gap | Gap | Why it is open | What would close it |
| --- | --- | --- | --- |
| G-01 | Live peer behaviour: whether real peers serve fetch packs on demand, and how many peers a node actually reaches. | No live node was run; the code only shows the request path. | A live run with peer logs and fetch-pack counts. |
| G-02 | Eclipse / poisoning outcome on the live network: what happens when all connected peers are stale, partial, or hostile. | Peer behaviour is outside the pinned source. | A controlled multi-node test with hostile peers. |
| G-03 | Real close cadence and the live value of `ledger_fetch_size_` for each node size. | `ledger_fetch_size_` comes from `SizedItem::ledgerFetch`, which varies by node size and was not traced. | Reading the sized-item table and measuring live close times. |
| G-04 | Live `minimumOnline` from SHAMapStore and how often it lets out-of-window ledgers be acquired. | `minimumOnline` is a runtime value from the SHAMap store. | A live run reporting `minimumOnline` over time. |
| G-05 | Fetch-pack bytes on the wire: real pack sizes and how often the 512-object cap binds. | The cap is code; the distribution of pack sizes is live data. | Instrumented `makeFetchPack` logging on a live node. |
| G-06 | Replay hash verification path: whether a replayed ledger's recomputed hash is compared with the validated hash, and where. | `LedgerReplayTask` internals were not traced in this pack. | A follow-up read of `LedgerReplayTask.cpp` and its tests. |
| G-07 | LedgerCleaner default ranges: which ledger ranges the cleaner is given by default and how `minRange_` / `maxRange_` are set at startup. | The cleaner is invoked with parameters; the defaults were not traced. | Reading the cleaner invocation sites and the RPC `ledger_cleaner` handler. |
| G-08 | Peer score distribution: how the latency-biased score is computed and whether a slow but honest peer can ever win a fetch-pack request. | `Peer::getScore` lives in the overlay code, outside the ledger files read here. | A read of the overlay scoring code plus live peer scores. |
