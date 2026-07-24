# 京麦快速上架 V2.1

## 用途

这是一个供 Codex 使用的京东京麦商品发布技能。它基于一个已经检查正确的模板商品，批量创建相近商品，修改标题、型号、价格、库存、图片、发货时间、退货和发票设置，并且只提交为暂不上架状态。

支持：

- 继承模板的通用主图和详情图；
- 全部换图、只换主图、只换详情图；
- 安全模式与页面稳定后的快速模式；
- 网络或浏览器中断后的断点恢复；
- 提交结果不明确时停止重试，避免重复创建商品。

## 使用方法

1. 下载本仓库，将文件夹放入 Codex 技能目录：

   ```text
   ~/.agents/skills/jingmai-fast-off-shelf
   ```

2. 复制并修改：

   ```text
   assets/run_config.template.json
   assets/products.template.csv
   ```

3. 准备运行清单并校验：

   ```powershell
   python scripts/prepare_run.py --products assets/products.template.csv --config assets/run_config.template.json --out run_manifest.json
   python scripts/validate_run.py run_manifest.json
   ```

4. 在 Chrome 中登录正确的京麦店铺，打开商品列表，并确认用于“发布相似品”的模板商品。

5. 在 Codex 中输入：

   ```text
   使用 $jingmai-fast-off-shelf，按照 run_manifest.json 从模板商品发布相近品，全部提交暂不上架。
   ```

6. 运行中断后输入：

   ```text
   使用 $jingmai-fast-off-shelf，读取 run_manifest.json，从上次断点继续。
   ```

账号登录、密码、短信验证码、验证码和权限确认需要用户本人处理。首次使用请先用少量商品验证店铺、类目、模板和各项设置。
