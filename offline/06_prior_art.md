# ⑥ 公开先例检索（2026-11-14）

检索式：`LineageOS self compiled kernel vendor touchscreen driver source rebuild porting case study`、`Android 自编译内核 触摸驱动 移植 vendor blob`。以下均为检索到的真实来源，标注「可借鉴点」，不编造结论。

## 与本项目最贴合的 3 个

**1. From locked kiosk to a self-built kernel: reviving the MLS MAIC, end to end**
https://milouk.me/projects/maic
> "Most of it was reverse-engineering: decompiling the stock drivers, **diffing symbol sizes against the stock binary byte for byte**, and working out what mine were doing that theirs quietly was not. Almost every fix is one or two tokens…"

可借鉴点：**方法完全一致** —— 反编译原厂驱动 + 逐字节符号尺寸差分，找自编译版少做的事。而且它踩的触摸坑和我们同源：
- `reset_chip()` 把一个「预期 NAK」的返回值累积进 `ret` 导致 probe 中止（芯片其实是好的）；
- `request_irq` 传 `IRQF_TRIGGER_RISING` 但 DT 声明 falling，且 request_irq 的 flag 会覆盖 DT 类型 ⇒ 触摸失效数天不可见（因为 debug 宏没编译）。
⇒ 直接印证我们 ① 的 `do_msm_restart` 尺寸差分方法，以及 ② 里 `irqflags` 缺 `IRQF_ONESHOT` / 触发方式与 DT 不一致的坑。

**2. Open Source Kernel for Xiaomi 12 / 12 Pro（Teamslow/manifest）**
https://github.com/Teamslow/manifest
> 官方内核源码不完整：Xiaomi 把 `hwid` 驱动加进 `.gitignore`，`fts_spi` 触摸驱动与 touchfeature 驱动的 Makefile 包含被注释；公开 fts 驱动「基本触摸输入可用」，但双击唤醒、UDFPS 不工作；触摸驱动 probe 早于 panel 导致 drm notifier 未注册。

可借鉴点：**同款 FTS 触摸驱动**，公开版基本功能可用但 gesture/屏下指纹残缺；「probe 顺序导致 notifier 未注册」与我们「触摸要等锁屏唤醒才生效」高度呼应。也说明「保留部分 vendor blob」是常态，不是失败。

**3. LeEco Le Max 2 (LEX820 / MSM8996) LineageOS 18.1 from-source port**
https://github.com/Pangu-Immortal/LeEco-LeMax2-LineageOS
> 同代骁龙 820 / MSM8996，从 LineageOS 源码重建 device tree、platform common、kernel 与 vendor blobs，跨 5 个大版本真机点亮 Android 11；README 明确「不吹牛红线」：只写真机可验证项，通话/数据/WiFi/相机标注「未插卡逐项实测，待验证」。

可借鉴点：**同 SoC 平台的完成度表述范式** —— 把「已验证 / 待验证」逐项列表，而不是笼统说「能开机」。我们的 `blm_tier3_coverage.py` 正是这个思路的可执行版本。

## 补充佐证

| 来源 | 与我们的关系 |
|---|---|
| XDA: Development of LineageOS and OSS Kernel for Xiaomi SM Gen 4/5.10 devices（https://www.xdaforums.com/t/rom-16-ksu-op9pro-crdroid-12-7-20-02-2026.4639597/post-89357813 ） | 开发者「reverse engineering the touchscreen drivers and got it working」，目标是 complete OSS kernel；同时说明 prebuilt 内核能靠 ABI 匹配加载 stock .ko，迁到源码构建后就得自己重建驱动 —— 正好对应我们上一轮「2 档+ 不可行」的结论 |
| Android 源码定制：编译 Pixel3 内核解决触摸/声音/WiFi 异常（http://mp.weixin.qq.com/s?__biz=MzU1NjYyNjA3MQ==&mid=2247485043... ） | 把触摸/声音/WLAN 驱动从 `=m` 改成 `=y` 编进内核后触摸恢复 —— 佐证我们坚持 built-in 而非 prebuilt .ko 的路线 |
| CSDN: Android 硬件抽象层（https://blog.csdn.net/gangjindianzi/article/details/109196846 ） | 只刷 boot.img 后 touch 失效，因触摸 .ko 在 vendor.img，必须 push 到 `/vendor/lib/modules/` —— 直接说明「内核与模块分离」会引入额外失效面 |

## [H] 综合判断（未实机验证）

- 公开案例里「自编译内核 + 触摸驱动源码化」是**可行但长尾**的路线，且几乎都保留 modem/DSP/GPU/TEE 固件 blob ⇒ 我们第 3 档定位合理，第 4 档「尽量无闭源 blob」在公开案例中也基本无人达成。
- 别人踩的坑（NAK 返回值、IRQ flag 覆盖 DT、probe 顺序、notifier 注册）与我们这轮遇到的高度重合 ⇒ 后续优先按这些模式排查，而不是继续猜 config。
- 完成度表述上，业界做法是「逐项真机可验证 + 明确标注未验证」，与本项目的 gate 三态一致。

## 边界

- 以上是检索结果摘要，未逐篇下载全文核验；引用语句来自搜索结果展示内容。
- 这些是 Android/ML 领域案例，不构成对本机 PD1610 具体寄存器/aboot 行为的证据。
