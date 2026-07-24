---
name: jingmai-fast-off-shelf
description: Create bounded batches of Jingdong/Jingmai seller products from one verified template in authenticated Chrome, change titles, models, prices, stock, selectively inherit or replace main/detail images, configure dispatch, return policy, and invoice restrictions, then submit only as temporarily off shelf. Use for 京麦商品发布, 京东卖家后台, 发布相似品, 通用主图和详情图复用, 批量上架前暂不上架, checkpointed resume, adaptive safe/fast execution, or recovery after network and Chrome interruptions without duplicating products.
---

# 京麦快速上架 V2.1

Create product records quickly while keeping every new product off shelf. Preserve the proven five-stage path as the safety fallback, use a three-stage warm path only after the current page profile is verified, and checkpoint every product and browser stage.

Never weaken these gates:

- Submit only `提交暂不上架`.
- Set `无理由退货` to exactly `不支持7天无理由退货`.
- Check `限制开专票` or `限制开专用发票`.
- Treat an unobserved submit result as unknown, not failed.

## Load only what is needed

1. Read [references/materials.md](references/materials.md) when preparing or transferring a batch.
2. Read [references/browser-workflow.md](references/browser-workflow.md) before controlling Chrome.
3. Read [references/network-recovery.md](references/network-recovery.md) only after a network, Chrome, or tab interruption.
4. Use `chrome:control-chrome` with its persistent browser runtime. Import `scripts/jingmai_browser_helpers.mjs` once by absolute path and reuse it.

## Prepare the complete batch first

Do not calculate titles, prices, or image choices while a publish form is open. Convert the source/template link and product data into a complete CSV or JSON manifest first. Set one explicit `image_strategy` for every product:

- `inherit_template`: keep the template's existing main and detail images; do not remove or upload images.
- `replace_all`: remove copied main/detail images and upload the listed replacements.
- `replace_main_only`: replace main images and preserve copied detail images.
- `replace_detail_only`: preserve copied main images and replace detail images.

Never infer image behavior from empty paths. Use the product value first, then the batch config default.

```powershell
python scripts/prepare_run.py --products <products.csv-or-json> --config <run_config.json> --out <run_manifest.json>
python scripts/validate_run.py <run_manifest.json>
python scripts/run_state.py summary <run_manifest.json>
```

Stop before browser work when validation reports an error.

## Browser preflight and page profile

1. Claim one existing authenticated `shop.jd.com` or `wares-jdm.jd.com` Chrome tab.
2. Verify the visible store name, template product ID, and category.
3. Keep one product-list tab. Never persist or hard-code a tab ID.
4. Build a page profile from the current URL plus stable visible anchors such as the store name, `商品列表`, the template product ID, and `发布相似品`.
5. Compare it with `run_state.py profile-show`.
6. Record the verified fingerprint:

```powershell
python scripts/run_state.py profile-verify <run_manifest.json> --fingerprint <FINGERPRINT>
```

Use `--allow-fast` only when the stored fingerprint matches the freshly observed profile and no interrupted or unknown submission is pending.

## Adaptive execution modes

### Safe mode: proven five-stage fallback

Use Safe mode for a new page profile, a changed page, an ambiguous locator, a failed gate, a restart without a matching profile, or any interruption:

1. **Open:** From a fresh product-list snapshot, locate the unique stable-template row and unique `发布相似品`, record the current tab list, click once, detect exactly one new JD seller tab, and return. Perform no form action.
2. **Acquire:** In a new browser call, acquire that discovered tab, wait for the unique title field, snapshot it, and return readiness.
3. **Fill:** Fill only manifest values and replace copied images.
4. **Gate:** Apply and read back all product fields, return policy, and invoice restriction.
5. **Submit:** In a new call, write the `submit_clicked` marker immediately before the click, click only `提交暂不上架`, wait for `publish-success`, and record `wareId`.

### Fast mode: verified three-stage warm path

Use Fast mode only after the current page profile is verified:

1. **Open:** Keep this as an isolated browser call exactly as in Safe mode.
2. **Acquire + Fill + Gate:** In the next call, acquire the new tab, verify the title field, fill the complete manifest item, apply both mandatory gates, and return structured readback. Do not submit in this call.
3. **Submit:** In a separate call, write the `submit_clicked` marker immediately before the click, submit off shelf, observe success, and checkpoint the `wareId`.

Fast mode never combines `Open` with later form work and never combines gate verification with submission. On any mismatch, invalidate the profile and return to Safe mode:

```powershell
python scripts/run_state.py profile-invalidate <run_manifest.json> --reason "<exact reason>"
```

## Per-product state machine

Claim before opening:

```powershell
python scripts/run_state.py claim <run_manifest.json> --sequence <N>
```

Record each reached browser stage:

```powershell
python scripts/run_state.py stage <run_manifest.json> --sequence <N> --stage opened --url "<current URL>"
python scripts/run_state.py stage <run_manifest.json> --sequence <N> --stage acquired
python scripts/run_state.py stage <run_manifest.json> --sequence <N> --stage filled
python scripts/run_state.py stage <run_manifest.json> --sequence <N> --stage gated
python scripts/run_state.py stage <run_manifest.json> --sequence <N> --stage submit_clicked
```

Fast mode may jump from `opened` to `gated` after one successful structured Acquire+Fill+Gate call. Never move a stage backward.

Treat `submit_clicked` as a write-ahead safety marker: record it immediately before clicking the final button so a crash between the click and the success page cannot trigger a blind duplicate retry.

After `publish-success?...wareId=<digits>`:

```powershell
python scripts/run_state.py record <run_manifest.json> --sequence <N> --ware-id <JD_WARE_ID>
```

## Mandatory per-product gate

For every form:

1. Replace the title, model/material number, price, stock, dispatch time, freight template, and other configured values.
2. Apply the declared image strategy:
   - for `inherit_template`, leave both image areas unchanged and verify inherited images remain present;
   - for `replace_all`, clear both areas and verify replacement order;
   - for `replace_main_only`, clear only main images and verify copied details remain;
   - for `replace_detail_only`, preserve main images and clear only details.
3. Set the visible return-policy control to `不支持7天无理由退货`.
4. Expand `其他设置` and check the invoice-restriction control.
5. Read back the actual controls. Do not infer values from config, template inheritance, the previous product, or visual styling.
6. Return a structured gate result including `image_strategy`. Submit only after all required values pass.

If any field or final button is missing, ambiguous, disabled, blank, or inconsistent, stop that item and fall back to Safe mode.

## Network and restart handling

On interruption, immediately record the observed stage:

```powershell
python scripts/run_state.py interrupt <run_manifest.json> --sequence <N> --stage <STAGE> --error "network disconnected"
python scripts/run_state.py resume-plan <run_manifest.json> --sequence <N>
```

- Before submit: reconnect, reclaim the verified product-list tab, and rebuild the trusted `商品列表 → 发布相似品` chain.
- At or after submit click without a success signal: verify whether the product already exists before any retry.
- Never mark an interrupted submit as failed and never blindly resubmit.
- Request manual action only when Chrome control cannot reconnect, a verified split click is still blocked, login/CAPTCHA/permission is required, the store is wrong, or the final button is ambiguous.

Follow [references/network-recovery.md](references/network-recovery.md) for exact recovery commands.

## Finish

1. Checkpoint each successful product immediately.
2. Process sequentially and report progress in chunks without reopening completed items.
3. Run one final summary and inspect only missing, unknown, or duplicated records.
4. Leave the product list on `已下架`, close task-created tabs, and finalize Chrome.

```powershell
python scripts/run_state.py summary <run_manifest.json> --expected-start <START> --expected-end <END>
```

Read [references/experience.md](references/experience.md) for the proven reliability lessons and V2 speed trade-offs.
