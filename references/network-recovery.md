# Network and Chrome interruption recovery

Use this procedure after a network disconnect, Chrome extension disconnect, stale tab, or lost browser binding. Do not bypass browser safety.

## Record first

Record the last stage that was actually observed:

```powershell
python scripts/run_state.py interrupt <run_manifest.json> --sequence <N> --stage <claimed|opened|acquired|filled|gated|submit_clicked> --error "network disconnected"
python scripts/run_state.py resume-plan <run_manifest.json> --sequence <N>
```

The `submit_clicked` stage is written immediately before the final click and automatically becomes `submission_unknown` after an interruption. This conservative write-ahead marker prevents a blind duplicate retry.

## Interruption before submit

1. Reconnect Chrome normally.
2. Discard the old tab binding. Do not reuse or guess its ID.
3. Claim the visible authenticated product-list tab.
4. Verify store name, template product ID, and the unique `发布相似品`.
5. Close only a task-created unsaved/stale publish tab when its identity is certain.
6. From a fresh product-list snapshot, click `发布相似品` in an isolated browser call.
7. In the next call, acquire the one discovered new tab.
8. Restart the same product from manifest values. Do not increment or skip to another product silently.

This restores the trusted click chain and should avoid asking the user to open the form manually when Chrome control is healthy.

## Interruption at or after submit

Do not reopen and submit immediately.

1. Search the product list by the exact model, cleaned title, and current sequence context.
2. If one matching off-shelf product exists, obtain its `wareId` and run:

```powershell
python scripts/run_state.py record <run_manifest.json> --sequence <N> --ware-id <JD_WARE_ID>
```

3. If a careful search proves the product was not created, clear the unknown state explicitly:

```powershell
python scripts/run_state.py clear-unknown <run_manifest.json> --sequence <N> --verified-not-created
```

4. Reclaim the product-list tab and restart from the verified template.
5. If the result remains ambiguous, stop. Do not risk creating a duplicate.

## True manual boundaries

Ask the user to intervene only for:

- login, password, SMS, CAPTCHA, or account-security checks;
- Chrome extension permission or browser connection that cannot be restored;
- store or account mismatch;
- a verified unique `发布相似品` click that the browser safety layer still blocks after one split retry;
- an ambiguous final button or unknown submission result that cannot be resolved from the product list.

Never hard-code publish URLs, reuse stale tab IDs, or claim that the skill can override Codex browser safety.
