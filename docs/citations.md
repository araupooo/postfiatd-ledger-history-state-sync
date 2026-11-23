# Citations

Public documentation consulted for the SPECIFIED rules, with verbatim
quotes. Accessed 24 Nov 2026. Each entry notes whether the code
agrees, and where it diverges the pack follows the code.

## S-01 — Capacity planning: 256 ledgers are enough to follow consensus

Source: https://jakeatripple.github.io/xrpl-dev-portal/capacity-planning.html
(XRPL.org capacity-planning documentation, mirrored.)

> "The [node_db] section in the rippled.cfg file sets the type of
> key-value store that rippled uses to hold the ledger store. ...
> An XRP Ledger server does not need to store more than the most
> recent 256 ledger versions to follow the consensus process and
> report the complete state of the ledger, but you can only query
> your server for transactions that executed in ledger versions it
> has stored locally."

Cross-check: agrees with the code default `LEDGER_HISTORY = 256`
(`src/xrpld/core/Config.h:224`). The docs figure is a deployment
statement, not a code fact. Rule R-39.

## S-02 — Ledger directory reference: peer delivery order

Source: https://xrplf.github.io/rippled/dir_7899ad0c658a3b97a951171682eee0fc.html
(rippled ledger directory reference.)

> "Peers deliver ledger data in the order in which the data can be
> validated. Data arrives in the following order: 1. The hash of the
> ledger header 2. The ledger header 3. The root nodes of the
> transaction tree and state tree 4. The lower (non-root) nodes of
> the state tree 5. The lower (non-root) nodes of the transaction
> tree"

Cross-check: agrees with the code — the header is requested first
(`InboundLedger::trigger`, `liBASE`), state is fetched before
transactions (comment at `InboundLedger.cpp:619`). Rule R-40.

## S-03 — Ledger directory reference: backfill only when caught up

Source: https://xrplf.github.io/rippled/dir_7899ad0c658a3b97a951171682eee0fc.html

> "The server prioritizes keeping up with current ledgers. But if it
> is caught up on the current ledger, and there are no higher priority
> demands on the server, then it will attempt to back fill its
> historical ledgers. It fills in the historical ledger data first by
> attempting to retrieve it from the local database. If the local
> database does not have all of the necessary data then the server
> requests the remaining information from network peers."

Cross-check: agrees with the `doAdvance` sync gates
(`LedgerMaster.cpp:1948-1955`) and the tryDB-then-peers order in
`InboundLedger::tryDB` (`InboundLedger.cpp:240-300`). Rule R-41.

## S-04 — Storage documentation: online_delete and fetch_depth

Source: https://git.inftf.org/ARCHIVE/rippled/src/commit/2881c08d2e18ffdbbdb1e4e591bc68cbf475aceb/src/xrpld/app/misc
(rippled source documentation, archived mirror.)

> "online_delete must not be greater than the [ledger_history]
> parameter. [fetch_depth] will be silently set to equal the
> online_delete setting if online_delete is greater than fetch_depth."

Cross-check: deployment guidance only. The code default for
`FETCH_DEPTH` is 1000000000 (`Config.h:225`); the clamp itself lives
in `SHAMapStore::clampFetchDepth`, which this pack did not trace.
Rule R-42.

## Divergence notes

- The docs say a server needs "the most recent 256 ledger versions"
  to follow consensus; the code default is the same 256, but the code
  additionally refuses to acquire anything more than 256 ledgers
  behind (`shouldAcquire`), which the docs do not state.
- The docs describe backfill as a low-priority activity; the code
  makes it strictly gated (validated age under 1 minute, valid ==
  published, write load under 8192, fewer than 10
  `jtPUBOLDLEDGER` jobs) — stricter than the docs wording.
- The docs do not mention the 100-ledger catch-up cap
  (`MAX_LEDGER_GAP`), the 512-object fetch-pack cap, or the 40-second
  fetch-pack refusal age; all three are code-only bounds.
