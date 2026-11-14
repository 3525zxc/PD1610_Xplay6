# ⑦ B0 交接基准与 GitHub 发布清单

日期 2026-11-14。用途：项目可随时停在此状态；接手者（人或模型）不需要重做本轮逆向调查。

## B0 定义（三条机器可判定）

> **2026-11-14 22:00 更新**：A 轮实机已完成，完成度从 `20/88` 收窄为确定值。以下以 A 轮后的 B0′ 为准，旧数字见 `flash_log/tier3_coverage_offline.json`（历史快照，勿再引用）。

1. `flash_log/tier3_coverage_roundA_final_strict.json`：**`score_lower=50`、`score_upper=50`**，`UNVERIFIED=0`，无 BLOCK。唤醒后对照口径 `..._final_awake.json` = `65/65`，仅用于说明触摸功能可用，**正式完成度采用严格 50**。
2. 设备：原厂 `3.18.71-perf-g8a8c60dd`、`sys.boot_completed=1`、`bootanim=stopped`、`vibrator-1-0=running`、9 个 input 设备齐全、**不在 fastboot**；回滚镜像 `929fda998547…` 已写入并验证，设备内 `/data/local/tmp/stock_boot.img` 副本 sha 一致。
3. 所有未验证项以 `UNVERIFIED` / `[H]` 标注；`05_experiment_queue.md` 写死 B–D 轮判据与统一采集清单；A 轮结果见 `offline/08_roundA_result.md`。

复核命令：
```bash
python tools/blm_round_capture.py --tag <roundNN> --image <boot.img> --score
python tools/blm_coldboot_verify.py --cycles 3 --report flash_log/<roundNN>_coldboot.json
python tools/blm_tier3_coverage.py \
  --baseline-input flash_log/stock_baseline_input_devices.txt \
  --baseline-i2c flash_log/stock_baseline_i2c_bindings.txt \
  --current-input flash_log/<roundNN>_input_devices.txt \
  --current-i2c flash_log/<roundNN>_i2c_bindings.txt \
  --props flash_log/<roundNN>_props.txt \
  --touch-events flash_log/<roundNN>_touch_events.txt \
  --nav-events flash_log/<roundNN>_nav_events.txt \
  --inventory offline/03_firmware_inventory.csv \
  --preflight images/boot_los16_blm_ftsirq_20261114192500.preflight.json \
  --boot-ok --hal-ignore init.svc.vivo-fingerprint-sh
python offline/04_evidence_audit.py
fastboot devices ; adb shell 'uname -r; getprop sys.boot_completed'
```

## 建议仓库结构

```
README.md                  真机验证状态表 + 不吹牛红线
NOTICE                     第三方资产清单（本仓库不包含）
LICENSE                    MIT（工具）/ CC-BY-4.0（文档）/ GPL-2.0（内核补丁）
HANDOFF.md                 交接 SOP（见下）
docs/rounds/               ROUND10–ROUND19 报告、时间线
docs/offline/              01–06 六份离线报告 + 本文件
tools/                     全部自研 Python / shell 工具
kernel/blm/                BLM 模块 C 源码与头文件
patches/                    fts.c / fts.h / cyttsp_button.c / msm-poweroff.c 的 .patch + config.diff
data/                      覆盖率 JSON、审计 JSON、符号差分 JSON、DTB 节点清单、固件清单 CSV
```

> **2026-11-14 23:10 用户决定变更**：改为「GitHub 全量公开文本细节 + 百度网盘全量冷备 + 一份 AI 资源索引」。生成好的可直接 push 目录是 `publish/`（verbatim 全量，213 文件 / 5.08 MiB），可选脱敏版 `publish_sanitized/`；全量分卷在 `archive/volumes/`（969 MiB / 2 卷），恢复 SOP 在 `archive/RESTORE.md`，给接手 AI 的索引是 `offline/12_ai_handoff_index.md`。下方白/黑名单保留作为**历史决策记录与二进制处理依据**，不再是发布操作手册。

## 发布白名单（自研或事实性数据）

- BLM 模块 C 源码、`tools/*.py`、`offline/*.py`、构建/刷机/回滚 SOP
- `ROUND*.md`、`offline/0*.md`、时间线、判定表、实验队列（原创文字）
- 覆盖率与审计 JSON、符号大小差分 JSON、`do_msm_restart` 调用表与字符串清单（**结论数据**，非原厂二进制）
- 从 DTB 解析出的节点/compatible 表、`blm_patch_dtb.py` / `blm_bypass_dtb.py`、补丁前后 diff 报告
- `03_firmware_inventory.csv`（仅文件名/大小/启发式分类，不含 blob 内容）
- 证据索引：文件路径 + sha256，**不附二进制本体**
- 内核补丁集（.patch）+ config diff + 构建脚本 + 已知缺口清单

## 发布黑名单（第三方二进制 / 设备唯一信息）

- `images/*.img`（含原厂 ramdisk 与 DTB 链）、原厂 `boot.img`、`offline/stock_Image.bin`（26 MB 原厂内核镜像）
- 332 个 `/vendor/firmware` / `/firmware` blob 本体、`fixtures/pd1610_81916_vivo.dtb`
- `flash_log/stock_kallsyms_addr.txt` 全量（原厂内核布局衍生）；只发筛出的 restart 相关符号子集
- `01_do_msm_restart.asm` / `_custom.asm` 全文含原厂指令字节；只发解析出的调用表与字符串 JSON
- `dmesg` / `logcat` / `getprop` / `dumpsys` 原文：含 `serialno`、fingerprint、securebootkeyhash、baseband 等，发布前必须脱敏
- `flash_log/blm_ram_round*.bin` 等物理内存 dump
- 任何可直接刷写的 boot.img

## 设备树与半成品内核的处理

- **设备树**：公开「解析结果 + 补丁工具 + diff 报告」，不公开原厂 DTB 二进制。若另行发布 DTS，注明是从原厂 DTB 反推的衍生描述与上游来源。
- **半成品内核**：公开补丁集 + config diff + 构建脚本 + 已知缺口，不公开整棵树或镜像。README 必须写明：导航键未通、触摸需锁屏唤醒后生效、reboot 通道未修、`b6d5debb…` 报过 bootloop 且原因未区分、最后一版 `864b0522…` 的 reboot 修复无效。

## HANDOFF.md 骨架

1. 设备当前状态 + 回滚 SOP（原厂镜像哈希、按约定「请进 fastboot」才手动进、USB 瞬断时停在 fastboot 不重启）
2. 每轮刷机 SOP：`blm_preflight.py` 17/17 → flash（失败重试不 reboot）→ reboot → 二次枚举确认 → 统一采集清单 → 跑覆盖率工具
3. A–D 四轮 claim / 量化判据 / 失败分支（直接引用 `05_experiment_queue.md`）
4. 未验证清单与已知坑：`adb reboot bootloader` 失效需手动、bootloop 回滚窗口、adb server 反复掉线需 `wait-for-device`、`kptr_restrict=2` 需 root 置 0
5. 证据索引：路径 → sha256，不含二进制
6. 接手第一条命令：从 `05_experiment_queue.md` 的 A 轮开始，先明确说「请进 fastboot」

## 边界

- B0′ 描述的是**可交接状态**，不是「第 3 档完成」；A 轮后 `UNVERIFIED=0`，但 `touch_cold` / `nav_keys` / `input_parity` / `i2c_parity` 四门仍 FAIL（严格 50 分）。
- `--hal-ignore init.svc.vivo-fingerprint-sh` 不能省：`init.vivo.fingerprint.rc` 里该服务是 `disabled`+`oneshot`，`stopped` 是正常终态，不加会把 `hal` 门误判 FAIL。
- 发布白名单里的报告含历史推断（如 Round14/15 的 usb_bam 归因已被 Round16 推翻），需在 README 标注归因演进，避免接手者误用旧结论。
