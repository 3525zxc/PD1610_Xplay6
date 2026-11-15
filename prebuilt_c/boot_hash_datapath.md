# boot 哈希输入的数据流追踪（2026-11-09 15:35）

> 目标：查清 `verify_image(data, len, "/boot")` 的 data 与 len 的真实来源
> 状态：**数据流已完整还原，但摘要仍无法复现**
> 环境：7.13.15 aboot（`b4d75a9b...`），基址 `0x91800000`

---

## 一、已还原的完整数据流

### 1.1 boot 缓冲区是固定地址

```
918011F0:  movw  ip, #0x51ac
918011F4:  movt  ip, #0x91b9
918011F8:  str   lr, [sp, #-4]!
918011FC:  sub   sp, sp, #0xc
91801200:  ldr   r2, [ip]
91801204:  mov   r0, #0x92000000      ← ★ 固定返回
91801208:  str   r2, [sp, #4]
...
91801220:  pop   {pc}
```

配套的 `0x91801228` 返回 `0x20000000`（另一个镜像区，可能是 recovery）。

**结论**：boot 镜像被读入 RAM 的固定地址 `0x92000000`。

### 1.2 len 由 boot header 页对齐计算

```
9183E204:  ldr   r3, [r4, #0x24]      ; page_size
9183E208:  cmp   r3, #0
9183E20C:  beq   0x9183E588
9183E21C:  cmp   r3, #0x1000          ; page_size 必须 ≤ 4096
9183E220:  bhi   0x9183EC28           ; 否则错误
9183E224:  sub   r2, r3, #1           ; r2 = page_size - 1（掩码）
9183E230:  str   r3, [r5]             ; 保存 page_size 到 0x91B93120
9183E238:  str   r2, [sb]             ; 保存掩码到 0x91B9CC0
9183E23C:  ldr   r1, [r4, #8]         ; kernel_size
9183E244:  ldr   r0, [r4, #0x10]      ; ramdisk_size
9183E24C:  strb  ip, [r4, #0x23f]     ; ★ ip=0，清 header+0x23F
9183E250:  add   r0, r3, r0           ; r3 = 掩码
9183E254:  add   r3, r3, r1
9183E258:  and   r3, r2, r3           ; (mask + kernel_size) & mask
9183E25C:  and   r0, r0, r2           ; (mask + ramdisk_size) & mask
9183E260:  str   r3, [sp, #0x18]      ; 对齐后 kernel 大小
9183E264:  str   r0, [sp, #0x1c]      ; 对齐后 ramdisk 大小
```

### 1.3 三个值汇合后传入验签

```
9183E268:  bl    0x918011F0           ; → r0 = 0x92000000
9183E280:  mov   r7, r0               ; r7 = data
9183E2A8:  ldr   r0, [sp, #0x18]      ; 对齐后 kernel
9183E2AC:  ldr   r1, [sp, #0x1c]      ; 对齐后 ramdisk
9183E2B0:  add   r3, r0, r1
9183E2B4:  add   sl, r3, ip           ; sl = kernel + ramdisk + page_size
9183E2B8:  bl    0x91839944           ; 验签封装（会读 is_unlocked）
9183E2C0:  cmp   sl, r3               ; 溢出检查
9183E2C8:  movw  r3, #0xffff
9183E2CC:  movt  r3, #0x917f          ; 0x917FFFFF
9183E2D0:  cmp   r7, r3
9183E2D4:  bhi   0x9183E598           ; data 边界检查
9183E2DC:  add   r2, sl, r7           ; end = data + len
9183E384:  mov   r0, r7               ; data
9183E388:  mov   r1, sl               ; len
9183E38C:  bl    0x91839B18           ; → verify_image
```

### 1.4 verify_image 与 verify_sig

```
0x91839B18（函数入口，r0=data, r1=len）
  91839B78:  bl   0x9181167C          ; verify_image(data, len, name)
      91811698:  mov  sb, r2          ; sb = 第 3 参数（实测为 "/boot" 字符串）
      918118E4:  mov  r3, sb
      918118EC:  bl   0x91810CB0      ; verify_sig(data, len, sig, name)
          91810CC4:  mov  sb, r0      ; data
          91810CD0:  mov  r8, r1      ; ★ len（函数原参数）
          91810D9C:  mov  r0, sb
          91810DA0:  mov  r1, r8      ; hash 长度 = len
          91810DAC:  bl   0x918215B4   ; hash dispatcher
              91821950:  mov  r8, r0
              91821958:  mov  r7, r1
              918219F0:  mov  r0, r8
              918219F4:  mov  r1, r7
              91821A04:  b    0x9186E294
                  9186E2BC:  mov  r6, r1
                  9186E2D0:  cmp  r6, #0    ; ← 判空，证明是长度
                  9186E2DC:  mov  r2, r6
                  9186E2E4:  bl   0x9186DEC8  ; update(ctx, data, len)
```

**关键结论**：`0x9186E294` 用 `cmp r6,#0 / beq` 判空——只有长度会这样判。**第二参数确实是长度，不是结束地址。**

### 1.5 公钥来源（非 boot 自带）

```
91839B60:  ldr   r3, [0x91B933A8]    ; 全局标志（静态初值 0）
91839B68:  movwne r2, #0xc08          ; 非0 → 0x91880C08 = "/survival"
91839B6C:  movweq r2, #0xc14          ; ==0 → 0x91880C14 = "/boot"
91839B78:  bl    0x9181167C
```

**第 3 参数是分区名字符串，不是公钥或证书指针。** `verify_image` 全程未接收证书 → 公钥来自 aboot 内部。

### 1.6 验签失败 → 阻断启动

```
91839B7C:  mov   r6, r0
91839B84:  cmp   r6, #0
91839B88:  beq   0x91839BA4          ; 成功
91839B8C:  movw  r3, #0x2d08
91839B90:  movt  r3, #0x91b9
91839B9C:  str   r1, [r3]            ; ★ skip_flag[0x91B92D08] = 1
```

加载器读取该标志：
```
9183A8:  cmp  r3, #0
9183AC:  bne  0x9183E5B8             ; 失败出口
```

**此前"该地址恒为 0、无写入"的结论已被推翻**——脚本漏掉了 `movw/movt` 隔几条指令再 `str` 的写法。

---

## 二、未解的矛盾

### 2.0 重要修正：len 实际是 0x3258000，不是 0x3257000（2026-11-09 15:48）

完整反汇编（0x9183E204–0x9183E2B8，无省略）暴露了此前的一个计算错误：

```
9183E248:  mov   ip, #0              ; strb 用的确实是真的 0
9183E24C:  strb  ip, [r4, #0x23f]
9183E250:  add   r0, r3, r0          ; r3 = mask = page_size-1
9183E254:  add   r3, r3, r1
9183E258:  and   r3, r2, r3          ; r2 = ~mask
9183E25C:  and   r0, r0, r2
9183E260:  str   r3, [sp, #0x18]     ; ALIGN(kernel)
9183E264:  str   r0, [sp, #0x1c]     ; ALIGN(ramdisk)
9183E268:  bl    0x918011F0
9183E27C:  ldr   ip, [r5]            ; ★ ip 被重新加载 = page_size（9183E230 存入 0x91B93120）
9183E2A8:  ldr   r0, [sp, #0x18]
9183E2AC:  ldr   r1, [sp, #0x1c]
9183E2B0:  add   r3, r0, r1           ; ALIGN(kernel) + ALIGN(ramdisk)
9183E2B4:  add   sl, r3, ip           ; ★ sl = 上式 + page_size
```

**寄存器状态表**：

| 地址 | r0 | r1 | r2 | r3 | ip | 备注 |
|---|---|---|---|---|---|---|
| E204 | — | — | — | page_size | — | 读 header+0x24 |
| E224 | — | — | mask | — | — | r2 = page_size-1 |
| E23C | — | kernel_size | — | — | — | |
| E240 | — | — | ~mask | mask | — | r2 = ~mask |
| E244 | ramdisk_size | — | ~mask | mask | — | |
| E248 | — | — | — | — | **0** | 显式清零 |
| E258 | — | — | ~mask | ALIGN(kernel) | 0 | |
| E25C | ALIGN(ramdisk) | — | ~mask | ALIGN(kernel) | 0 | |
| E27C | — | — | — | — | **page_size** | ldr ip,[r5] 重载 |
| E2B0 | ALIGN(kernel) | ALIGN(ramdisk) | — | 两者之和 | page_size | |
| E2B4 | — | — | — | — | page_size | sl = 和 + page_size |

**代入 1.15.1 数值**：

```
ALIGN(kernel_size=0x2B1B4FC, 0x1000)  = 0x2B1C000
ALIGN(ramdisk_size=0x73Axxx, 0x1000)  = 0x73B000
sl = 0x2B1C000 + 0x73B000 + 0x1000    = 0x3258000
```

**此前一直用的 `0x3257000` 少了 4096 字节。**

这一步是 GPT 质疑 `strb ip` 不能证明 `ip=0` 促成的——虽然它推的 `ip=-page_size` 不对（反汇编里 `9183E248: mov ip,#0` 是显式的，只是随后在 `9183E27C` 被重载为 `page_size`），但**质疑的方向是对的**，逼出了这个计算错误。

### 2.1 摘要仍对不上

目标（签名 raw RSA 解出的 DigestInfo 中 32 字节）：

```
1cf2d759c00f4761740653f58f9bd4b7aeb112cf37212d3aad50a4b6339e5da4
```

用修正后的长度重试：

| 构造 | SHA-256 前 44 hex |
|---|---|
| `boot[0:0x3258000]` | `6cca3cae9c25fbf5be2c91871b3585c1fced19cb7477` |
| `boot[0:0x3257000] + 4096×00` | `f04d4c81ee76ce58b5635867830d06ca56827ec348f5` |
| `boot[0:0x3257000] + 尾部1280 + 填充` | `bc64795cd6e15b93eb845c13813a1ad1f92e451073d1` |

全部不匹配。

### 2.1.1 这里出现一个逻辑矛盾

`sl = 0x3258000` 意味着哈希覆盖 `[0, 0x3258000)`，而证书块起始于 `0x3257000`——**签名会覆盖它自己**，这在密码学上不可能。

因此只有两种解释：

1. 设备上 `0x3257000..0x3258000` 这 4096 字节在验证时**不是文件里的证书块**（可能是 0，或上一次启动的残留）
2. `sl` 的计算还有我没看清的环节（尽管寄存器表已经走完一遍）

第 1 条又回到「设备分区内容 vs 包内文件」的问题。

### 2.2 已排除的可能

| 假设 | 排除依据 |
|---|---|
| `0x23F` 清零改变了哈希 | 该字节原值就是 `00`，清零无影响 |
| `0x91810814` 修改缓冲区 | 只写 `[某结构+9]`，不碰 boot 缓冲区 |
| 分块/双哈希 | 试过 8 段均分、4MB 分块、4KB Merkle 根、累积前缀，全部不匹配 |
| `(start, end)` 语义 | update 用 `cmp r6,#0` 判空，是长度 |
| aboot 硬编码偏移 | 搜 `0x3257000`/`0x3257500`/`0x3258500`/`0x32A7000`/`0xE30000`/`0x3801000`，`movw/movt` 零命中 |
| 30+ 种数据范围组合 | 1页/kernel/ramdisk/分区边界/96MB全量/header字段清零，全不匹配 |

### 2.3 剩余可能（按怀疑度）

| 可能 | 怀疑度 | 理由 |
|---|---|---|
| 设备 boot 分区前 0x3258000 字节与包内 boot.img 不一致 | **高** | 所有长度修正都试过，仍不匹配 |
| 0x3257000..0x3258000 在内存中被改写（清 0 或换内容） | 中高 | 否则签名会覆盖自己 |
| 读取函数 `0x9180FF90` 或其上游对数据做了跳段/拷贝 | 中 | 尚未彻底还原 |
| SHA-256 实现本身错误 | 低 | raw RSA、DigestInfo、算法结构全部吻合 |

---

## 三、额外 256 字节（签名块之后）

### 3.1 布局（四个样本一致）

```
+0x000 .. +0x500   1280 B   SEQUENCE（version + cert + algo + params + sig）
+0x500 .. +0x600    256 B   未知数据（全非零）
+0x600 .. +0x1500  3840 B   全零
总计 5376 B = 0x1500
```

`1280 + 256 = 1536`，`1536 + 3840 = 5376`。后两部分合计正好 4096。

### 3.2 已排除

| 假设 | 结果 |
|---|---|
| 第二个 RSA 签名 | raw 模幂（大小端）均非 PKCS#1，非 PSS |
| 分块哈希表（8×32B） | 试了均分/4MB/4KB Merkle/累积前缀，全不匹配 |
| 等于某个已知摘要 | 不等于 `sha256(boot[0:0x3257000])` 或 `sha256(boot[0:0x3257500])` |

熵 7.22 bits/byte，接近随机。

### 3.3 aboot 未硬编码该偏移

搜索所有尾块偏移常量（`movw/movt` 组合），**零命中**。说明不是 aboot 按固定地址读取的。

---

## 四、下一步（待设备恢复）

### 4.1 决定性验证：EDL/Firehose 只读回读 boot 分区

```
进入 9008
  → 加载 prog_ufs_firehose_8996_ddr.elf
  → 读 GPT 定位 boot（LUN4 / start_sector 47370 / 24576 sectors）
  → 只读回读整个 boot 分区（96 MB）
  → 保存 boot_partition_dump.bin
  → 与 boot_00_baseline.img 逐字节比对
```

**只做 read，不 program / write / erase。**

比对内容：

| 项 | 说明 |
|---|---|
| 前 0x3258000 字节 SHA-256 | 与签名摘要比对 |
| 与包内 boot.img 的差异字节数 | 定位第一个差异偏移 |
| `0x3257000..0x3258000` 的实际内容 | 验证「签名是否覆盖自己」这个矛盾 |

如果设备分区与文件完全一致 → 说明 aboot 做了未发现的转换，需 Unicorn 仿真
如果不一致 → 记录差异位置，反推是 fastboot 写入时改的还是本来如此

### 4.2 旁路验证：fastboot fetch

```
fastboot getvar max-fetch-size
```

若返回有效值，可尝试 `fastboot fetch boot boot_dump.img`。该命令只读，低风险。
但这台设备的 aboot 年代较早，很可能不支持。

### 4.3 静态待补

1. `0x918098A0` / `0x918099CC` / `0x91809A44` —— boot 数据的实际读取路径（读到哪个地址、读多少）
2. `0x91839B18` 入口到 `0x9181167C` 之间，是否改写了 r0/r1（目前看到 `mov r7, lr`，未影响参数）
3. 确认 `boot.img[0x18:0x1C]`（second_size）是否为 0

---

## 五、材料位置

| 文件 | 说明 |
|---|---|
| `C:\qfilx\probe\aboot.bin` | 7.13.15 aboot（16 MB） |
| `C:\qfilx\boottest\boot_00_baseline.img` | 1.15.1 boot.img（52,790,528 B） |
| `C:\qfilx\exp\boot_full.bin` | 7.13.15 boot 分区完整 dump（96 MB） |
| `C:\qfilx\firmware\81916\boot.img` | 8.19.16 boot.img |
| `aboot_verify_disasm_excerpt.md` | 反汇编摘录（含 `blx ip` 未解结构） |
