# Materials and environment

## Prepare on every computer

- Current Codex desktop, Google Chrome, and `chrome:control-chrome`.
- Chrome extension enabled for the seller site and local file URLs.
- Chrome already logged into the correct Jingmai/JD seller account.
- `商品列表` open before the run.
- Stable network. The user handles CAPTCHA, SMS, passwords, account security, and permission prompts.

## Prepare for every batch

1. Store name exactly as visible in Jingmai.
2. Bounded product sequence range.
3. One stable template product ID from the correct category.
4. Fixed category, authorized brand, stock, dispatch time, freight template, overseas-sale setting, return policy, and invoice restriction.
5. CSV or JSON product list containing final title, model, price, stock, and image paths.
6. Final processed images stored locally only for products whose image strategy requires replacement.
7. Explicit authorization to use only `提交暂不上架`.

## Product fields

Required:

- `sequence`: unique integer.
- `title`: final or source title.
- `model`: model/material number when the page requires it.
- `price`: positive yuan amount.
- `stock`: non-negative integer, or use configured default.
- `image_strategy`: one of `inherit_template`, `replace_all`, `replace_main_only`, or `replace_detail_only`.

Optional:

- `main_images` or `main_images_json` when replacing main images.
- `detail_images` or `detail_images_json` when replacing detail images.
- `source_url`
- `attributes_json`
- `dispatch_time`; defaults to config.

Image rules:

- `inherit_template` requires no local image paths.
- `replace_all` requires main images; detail images default to the first main image when omitted.
- `replace_main_only` requires main images and must not provide detail replacements.
- `replace_detail_only` requires detail images and must not provide main replacements.
- Image lists may be JSON arrays or pipe-delimited absolute paths. Supported formats are PNG, JPG, JPEG, and WEBP.

## Transfer or restart

1. Keep the run manifest with the product/image files.
2. Do not transfer cookies, browser profiles, or tab IDs.
3. After restarting Codex, run `run_state.py summary`, `profile-show`, and `resume-plan` for any active or interrupted sequence.
4. Reconnect to the existing Chrome seller tab and verify store/template/page anchors.
5. Use Fast mode only after the fresh page profile matches; otherwise use Safe mode.
