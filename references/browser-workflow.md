# Proven Chrome workflow with adaptive speed

## Bootstrap once

- Use the Chrome skill and keep its browser binding for the whole batch.
- Claim the user's existing authenticated tab; do not open a second browser profile.
- Resolve and import `scripts/jingmai_browser_helpers.mjs` once by absolute path.
- Keep one verified product-list tab and one temporary publish/success tab.
- Never store or hard-code a tab ID across restarts.

## Stable-template rule

Search `config.template_ware_id` in `商品列表` and open `发布相似品` from that same template for every product. Never copy the product just created.

## Page profile

Build the profile from the current allowed JD seller URL and stable visible anchors:

- configured store name;
- `商品列表`;
- configured template product ID;
- unique `发布相似品`.

Persist only the fingerprint and verification time. Tab IDs and active form objects are ephemeral. If the fresh fingerprint differs, invalidate the profile and use Safe mode.

## Safe mode

Use five browser executions:

1. **Open:** Snapshot the product list, verify one template row and one `发布相似品`, capture before/after tab lists, click once, and return the one discovered new tab.
2. **Acquire:** In a new call, acquire that exact tab, accept a button-generated `/newPublish/` to `/popPublish/` rewrite, wait for one title field, and return readiness.
3. **Fill:** Fill manifest values and apply the item's explicit image strategy.
4. **Gate:** Apply and read back all fields plus the two mandatory controls.
5. **Submit:** In a new call, persist the `submit_clicked` write-ahead marker, click only `提交暂不上架`, observe success, and record `wareId`.

Never combine Open with a later stage.

## Fast mode

Use three browser executions only when the current profile is verified:

1. **Open:** Same isolated call as Safe mode.
2. **Acquire + Fill + Gate:** Acquire the discovered tab, verify the title field, perform all form work, then return a structured readback. Do not submit.
3. **Submit:** Persist the `submit_clicked` write-ahead marker, then submit only after the gate result has returned successfully.

Fall back to Safe mode when a locator is missing or ambiguous, the route family changes, an overlay cannot be closed, a field does not read back, a network error appears, or submission behavior changes.

## Field sequence

1. Close informational overlays after readiness is proven.
2. Fill title, model/material attributes, price, and stock.
3. Apply exactly one media branch:
   - `inherit_template`: do not open deletion/upload actions; verify inherited main and detail images remain populated.
   - `replace_all`: remove copied main/detail images, then upload `main_images` and `detail_images` in order.
   - `replace_main_only`: remove and replace only main images; verify copied detail images remain populated.
   - `replace_detail_only`: preserve main images; remove and replace only detail images.
4. Set dispatch time, freight template, and overseas-sale value.
5. Set `无理由退货` to exactly `不支持7天无理由退货`.
6. Expand `其他设置`, locate `限制开专票` or `限制开专用发票`, and check it.
7. Read the actual controls, declared `image_strategy`, and all changed product fields back.
8. Submit only in the following browser call.

Do not treat inherited template images as old images that must be deleted. Delete media only when the selected strategy requires replacement.

## Success and retry

- Treat `publish-success?...wareId=<digits>` as immediate success.
- Record `submit_clicked` immediately before the final click; this intentionally forces verification after a crash even when the click outcome is uncertain.
- Record the ware ID before opening another form.
- If the first submit click is consumed by a visible identity-verification success message, click the same off-shelf button once more on the unchanged gated form.
- If stock inheritance produces a false validation error, discard the unsaved form and reopen from the stable template.
- On network or browser interruption, stop normal retry logic and follow `network-recovery.md`.
