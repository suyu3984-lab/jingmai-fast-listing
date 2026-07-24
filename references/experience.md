# Proven lessons and V2 optimization

- The original five-stage workflow completed a verified 24/24 batch with every product off shelf, no loss, and no duplicates. Keep it as the safety fallback.
- The largest reliability improvement remains one fixed known-good template. Copying newly created products propagated stale SKU and stock state.
- The original five-stage rule also creates at least five browser round trips per product. V2 reduces this to three only after a page profile is freshly verified.
- Always keep Open isolated. The verified failure pattern came from combining the template click and later form actions across a navigation boundary.
- Browser warmth is session state, not permanent learning. After restart, reconnect and verify anchors before using Fast mode.
- Persist fingerprints and product stages, but never persist tab IDs or assume an unfinished form is trustworthy after interruption.
- A network disconnect after submit is more dangerous than a normal failure. Mark it `submission_unknown` and search for an existing product before retrying.
- Preparing all titles, prices, and ordered main/detail image lists before browser work reduces both token and UI time.
- Reuse truly generic template media with `inherit_template`; unnecessary deletion and re-upload wastes time and can disturb a proven image order.
- Make media reuse explicit per product. Never assume that a blank image path means "keep template images."
- DOM-backed Chrome control remains faster and more stable than coordinate automation.
- Product-level checkpoints are mandatory. Never rerun a completed sequence.
- Fast mode must retain per-product readback for return policy and invoice restriction.
- Run one final missing/duplicate audit instead of repeatedly reviewing the warehouse after every item.
