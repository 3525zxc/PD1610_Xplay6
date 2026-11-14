# ② input parity 缺口 —— 剩余 3 项可行性判定

## [O] 观察

原厂 9 个 input 设备，自编译 `#9` 5 个（`flash_log/stock_baseline_input_devices.txt` vs `round24_ftsirq_input_devices.txt`）：

| 缺失设备 | 原厂来源 | 自编译侧证据 | 判定 |
|---|---|---|---|
| `vivo_virtual_key` | `3-0028` / `cyttsp,cyttsp-button` | `CONFIG_TOUCHSCREEN_CYTTSP_BUTTON=y` 已开、`3-0028` 已绑定、DT 解析全过、I²C 读到 `hw_version=0x84`；卡在 `request_threaded_irq` 缺 `IRQF_ONESHOT`（`cyttsp_button.c:1473`，`irqflags` 来自 DT 的 `2`=仅 FALLING） | **可修，最小改动**：补 `irqflags \|= IRQF_ONESHOT`。最后一版 `b6d5debb…` 另把 pinctrl 宏改 `default` 后报 bootloop，原因未区分（见 ⑤ 轮 A） |
| `goodixfp` | `/soc/spi@75B9000/goodix_gf5116m@1`，compatible `goodix,fingerprint` | 原厂 config 有 `CONFIG_BBK_FINGERPRINT=y` / `BBK_FP_ID` / `BBK_GF5116M`；自编译 config 只有 `# CONFIG_INPUT_FINGERPRINT is not set`，`System.map` 里 `goodix\|gf5116\|bbk_fp` 符号 **0 个**（原厂 kallsyms 10 个） | **最重**：vivo 私有驱动，开源树完全没有源码。需要按 ① 的方法反汇编原厂 SPI 驱动 → 重建 C，或从公开 Goodix GF5116M 驱动改写。工作量大，是第 3 档真正的大头 |
| `msm8996-tasha-cdp-snd-card Headset Jack` / `Button Jack` | `/soc/sound-9335`，compatible `qcom,msm8996-asoc-snd-tasha` | 两边 `CONFIG_SND_SOC_MSM8996=y`；自编译 `System.map` 里 `tasha\|snd_card` 符号 **346 个**（原厂 258），驱动在 | **中等可修**：不是缺驱动，是 machine driver / jack-detection 注册路径或 DT 属性差异。先对比两边 dmesg 的 `ASoC`/`wcd` 注册日志与 `snd_soc_*` 符号即可定位 |

## [H] 判定（离线假设，未实机验证）

- 3 项里 **1 项小改（虚拟键）、1 项中等（声卡 jack）、1 项重（指纹移植）**。
- 按完成度工具 `input_parity` 这一门（权重 12）：修好前两项可到 7/9，指纹未补则该门仍是 FAIL —— 这一门天然是第 3 档的长尾。
- 顺序建议：虚拟键 → 声卡 jack → 指纹。前两项不依赖实机新增硬件知识，第三项要先做 ① 那样的原厂二进制逆向。
- 原厂 `/proc/config.gz` 与自编译 `.config` 的私有项差分已落盘：`flash_log/stock_baseline_config.txt` / `custom_config.txt`。

## 边界

- 「可修」是离线可行性判断，**未实机验证**（最后一版 `navfinal` 报 bootloop 后已回滚原厂）。
- 原厂 kallsyms 地址取自临时 `kptr_restrict=0`，仅用于符号存在性统计，未做函数级反汇编。
