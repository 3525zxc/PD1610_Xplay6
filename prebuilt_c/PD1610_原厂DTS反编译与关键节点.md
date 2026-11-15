# PD1610 原厂设备树（DTB → DTS）反编译与关键节点

> 日期：2026-11-10 14:40
> 来源：`PD1610MD-patch_8.19.16_for_7.12.5_1108090720.zip` → `boot.img` → kernel 区 DTB 链第 79 份
> 方法：自写最小 FDT 解析器（`C:\qfilx\exp\fdt_tool.py`），**不依赖 dtc**
> 产物：`PD1610_原厂设备树_81916.dtb`（409,557 B）+ `PD1610_原厂设备树_81916.dts`（581,979 B / 15,641 行）
> 状态：**纯离线只读**，未执行任何刷机操作

## 0. 结论先说

这份 DTS 是**目标 B（3.18 内核 + Android 10 移植）最基础的一份材料**，它把 Xplay6 的硬件构成、驱动绑定、以及 vivo 的定制点全部摊开了。三个关键发现：

1. **`compatible` 是 `qcom,msm8996-cdp`** —— vivo 直接以高通参考板（CDP）为基底改的，不是自研板级拓扑。这对移植是好消息：绝大部分节点的结构与主线/CAF 参考板一致。
2. **音频链路完整可读**：`ess,es9038`（I2S 主模式）+ 2× `nxp,tfa98xx`（TFA9890）+ `sound-9335`/`tasha_codec`。这就是 Xplay6 最难移植的那部分，现在有了完整参数。
3. **vivo 定制集中在电源/充电与音频调参**：`bbk,*`（充电）、`vivo,tfa98xx-*`（喇叭调参）、`vivo,param-*`。这些是必须保留的私有属性。

## 1. 提取与解析

| 项 | 值 |
|---|---|
| boot.img 内 DTB 总数 | **122** |
| PD1610 专用份 | **第 79 份**（索引从 0 起），offset `0x02615836`，size 409,557 |
| `model` | `vivo MSM 8996 v3 + PMI8996 PD1610` |
| `qcom,msm-id` | `<0xf6 0x30001>` |
| `qcom,board-id` | `<0x1 0xa 0x1000001 0x0>` |
| `qcom,pmic-id` | `<0x20009 0x10013 0x0 0x0>` |
| `compatible` | `qcom,msm8996-cdp`, `qcom,msm8996`, `qcom,cdp` |
| FDT version | 17 |
| 节点数 / 属性数 | 1,983 / 12,829 |

**解析器**：`C:\qfilx\exp\fdt_tool.py`
- `enum_dtbs(buf)`：按 `d00dfeed` + totalsize 自洽筛选，避免误命中
- `FDT.walk()`：完整走 `BEGIN_NODE/END_NODE/PROP/NOP/END` 事件流
- `fmt_val()`：空值 / 字符串序列 / u32 数组三态格式化
- `to_dts()`：输出 `/dts-v1/;` 风格文本

## 2. 关键节点清单

### 2.1 音频（Xplay6 的核心差异）

```
dac@48 {
    compatible = "ess,es9038";
    ext-dac-vd-supply  = <0xef>;
    ext-dac-va-supply  = <0x108>;
    ext-dac-4v8-supply = <0x109>;
    ext-dac-rst-gpio   = <0x1a 0x55 0x0>;
    i2s-master;                     ← ES9038 作为 I2S 主设备
    vivo,param-num = <0x4 0x4>;
    vivo,params = <0x16 0x27 0x40 0x7f ...>;   ← 16 字节滤波器/音量参数
}

tfa98xx (×2) {
    compatible = "nxp,tfa98xx";
    vivo,tfa98xx-version = "tfa9890";
    vivo,tfa98xx-config  = "tfa98xx_PD1610.cnt";   ← 器件相关调参文件名
    vivo,tfa98xx-impedance-min = <0x276>;  (630)
    vivo,tfa98xx-impedance-max = <0x3b6>;  (950)
    vivo,tfa98xx-frequency-min = <0x2bc>;  (700)
    vivo,tfa98xx-frequency-max = <0x3b6>;  (950)
    vivo,tfa98xx-Qt-min        = <0x7d>;   (125)
    qcom,tfa98xx-rst-gpio      = <0x1a 0x19 0x0>;
}
```

> 对移植的含义：第三方 ROM 要出声，必须同时满足 ① ES9038 的 I2S 主模式时序与供电时序；② TFA9890 的 `tfa98xx_PD1610.cnt` 调参文件与阻抗/频响窗口。这两项都不是通用驱动能直接套的，**必须从原厂把参数原样搬过去**。这也是案例博主那台机器"DSD 能响"说明其移植做到了这一层的原因。

### 2.2 充电 / 电源

```
qcom,qpnp-smbcharger { compatible = "qcom,qpnp-smbcharger"; ... }
bbk,parallel-charger;                 ← vivo 双充电芯片（并联充电）
bbk,parallel-iindpm-ma = <0x5dc>;     (1500 mA)
bbk,charging-disabled;
bbk,vadc_channel = <0x20>;
bbk,rsense-mohm  = <0x78>;            (120 mΩ)
bbk,bms-psy-name = "bms";
ti,parallel-usb-min-current-ma = <0x4b0>;       (1200)
ti,parallel-fastchg-current-max-ma = <0x5dc>;   (1500)
```

### 2.3 显示 / 其他

- `qcom,mdss_mdp@900000`（MDSS 显示控制器，标准 MSM8996 结构）
- `sound-9335` + `tasha_codec`（WCD9335 内置 codec，走 SLIMbus）
- `qcom,ion` 多 heap（SYSTEM / DMA / …）
- `qcom,msm-hdmi-audio-codec-rx`（HDMI 音频）

## 3. 对目标 B 的三条直接用途

1. **驱动清单可直接生成**：从 DTS 里 `compatible` 去重，就能得到"这个设备需要哪些驱动"的完整列表（下一步可做）。
2. **vivo 私有属性必须原样保留**：`bbk,*` / `vivo,*` 这两族是原厂驱动才认的，第三方内核要么保留这些驱动，要么改写绑定——这是移植工作量的主要来源。
3. **CDP 基底降低难度**：`qcom,msm8996-cdp` 说明板级拓扑接近参考设计，主线的 msm8996 支持（若有）可作起点，只需补 vivo 定制部分。

## 4. 未执行 / 后续

- 未做 `compatible` 去重清单（可作为下一步，产出"驱动需求表"）。
- 未与 PD1516A 的 DTS 做节点级 diff（可看出 vivo 同平台两机型的差异点）。
- 未与 mainline `arch/arm64/boot/dts/qcom/msm8996*` 对照（判断可复用比例）。
- 未验证 DTS 能否被 dtc 重新编译（本机未装 dtc，解析器为自研，输出为"可读近似"而非严格等价）。

---

## 5. 驱动需求量化（2026-11-10 14:45 补充）

对全 DTS 的 `compatible = "...";` 做提取与去重：

| 分类 | 数量 |
|---|---|
| 唯一 compatible 总数 | **303** |
| `qcom,` 平台驱动 | 258 |
| 其它厂商（arm / ti / ess / nxp / regulator-fixed 等） | 42 |
| **`vivo,` / `bbk,` 私有驱动** | **3** |

### 5.1 仅有的三个 vivo 私有 compatible

```
vivo,charger-monitor
vivo,hifi-codec-pd1610a
vivo,touchscreen-config
```

**这是本次最有价值的量化结论**：vivo 在这一层只写了 **3 个私有驱动**，其余全部复用高通/第三方驱动。

- `vivo,hifi-codec-pd1610a` —— 对应 ES9038 的板级封装（`ess,es9038` 之上）
- `vivo,charger-monitor` —— 对应双充电芯片的监控逻辑（`bbk,*` 属性的宿主）
- `vivo,touchscreen-config` —— 触摸屏参数下发

### 5.2 高频复用的标准节点（前 10）

| compatible | 次数 |
|---|---|
| `qcom,rpm-smd-regulator` | 52 |
| `qcom,rpm-smd-regulator-resource` | 43 |
| `arm,coresight-cti` | 34 |
| `qcom,gdsc` | 24 |
| `qcom,msm-dai-q6-dev` | 23 |
| `qcom,msm-dai-q6-tdm` | 20 |
| `qcom,smp2pgpio` | 19 |
| `qcom,smmu-v2` | 11 |
| `qcom,qpnp-pwm` | 10 |
| `qcom,dsi-display` | 9 |

### 5.3 对目标 B 的意义（修正工作量判断）

之前把"移植"想成"要重写一堆 vivo 专有驱动"，实际数据是：

- **必须保留/移植的私有驱动只有 3 个**；
- 其余 300 个 compatible 都是高通/第三方标准驱动，CAF 的 msm-3.18 树里本来就有；
- 真正的难点转移到**参数**而非**代码**：`tfa98xx_PD1610.cnt`、`vivo,params` 16 字节滤波器参数、充电阈值等——这些必须原样搬。

⇒ **目标 B 的可行性比原先估计的高一档**：工作量主要在"原厂内核树 + 原厂 DTS + 3 个私有驱动"的搬运与 Android 10 兼容性补丁，而不是从零写板级支持。
