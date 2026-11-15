# aboot 验签链反汇编摘录（供独立复核）

> 文件：`C:\qfilx\probe\aboot.bin`（7.13.15，16 MB 分区 dump，ELF32 ARM）
> SHA256：`b4d75a9b399a8d28b8bd7ff7c68994beadab708ed3d23d4c399095788efc3c5f`
> 基址：`0x91800000`，文件偏移 `0x8000` 起为代码段
> 工具：capstone（ARM mode，skipdata）

本摘录聚焦一个尚未解释的结构：`0x9186CC54` 中对「分区名指针 +8」的间接调用。

---

### 1. verify_image 的调用点（含区分区内核/启动路径的条件）

```asm
91839B58  movw     r3, #0x33a8
91839B5C  movt     r3, #0x91b9
91839B60  ldr      r3, [r3]                   ; 读全局标志 0x91B933A8（静态初值 0）
91839B64  cmp      r3, #0
91839B68  movwne   r2, #0xc08                 ; 非0 时 r2 = 0x91880C08
91839B6C  movweq   r2, #0xc14                 ; ==0 时 r2 = 0x91880C14
91839B70  movtne   r2, #0x9188
91839B74  movteq   r2, #0x9188
91839B78  bl       #0x9181167c                ; verify_image(data=r0, len=r1, name=r2)
91839B7C  mov      r6, r0                     ; 保存返回值
91839B80  bl       #0x91811af0
91839B84  cmp      r6, #0
91839B88  beq      #0x91839ba4                ; 返回 0 → 成功，继续
91839B8C  movw     r3, #0x2d08
91839B90  movt     r3, #0x91b9
91839B94  mov      r1, #1
91839B98  mov      r2, #0
91839B9C  str      r1, [r3]                   ; ★ 失败：skip_flag[0x91B92D08] = 1
91839BA0  str      r2, [r4, #0x14]
91839BA4  bl       #0x91811ab0
91839BA8  cmp      r0, #2
91839BAC  beq      #0x91839c34
91839BB0  cmp      r0, #3
91839BB4  beq      #0x91839c1c
91839BB8  ldr      r3, [r4, #0x14]
91839BBC  cmp      r3, #0
```

### 2. verify_image 开头

```asm
9181167C  push     {r4, r5, r6, r7, r8, sb, sl, fp, lr}
91811680  movw     r4, #0x51ac
91811684  movt     r4, #0x91b9
91811688  sub      sp, sp, #0x2c
9181168C  add      r8, r0, r1                 ; r8 = data + len
91811690  mov      r7, r1                     ; r7 = len
91811694  ldr      r3, [r4]
91811698  mov      sb, r2                     ; ★ sb = r2（第 3 参数，实测为 "/boot" 字符串）
9181169C  str      lr, [sp, #8]
918116A0  mov      r6, r0                     ; r6 = data
918116A4  str      r8, [sp, #0x1c]
918116A8  str      r3, [sp, #0x24]
918116AC  bl       #0x918107c4
918116B0  bl       #0x9184fb9c
918116B4  subs     r5, r0, #0
918116B8  beq      #0x91811a84
918116BC  ldr      sl, [sp, #0x1c]
918116C0  bl       #0x918107c4
918116C4  mov      r1, sl
918116C8  mov      r2, r0
918116CC  mov      r0, r5
918116D0  bl       #0x9184fd8c
918116D4  bl       #0x918107c4
918116D8  cmp      r0, #2
918116DC  bhi      #0x91811824
918116E0  movw     r0, #0x9878
918116E4  movt     r0, #0x9187
918116E8  bl       #0x9184e550
918116EC  movw     r3, #0xf4a0
918116F0  movw     r1, #0x46c8
918116F4  movt     r3, #0x9187
918116F8  movt     r1, #0x9187
918116FC  str      r3, [sp]
91811700  movw     r2, #0x96b8
91811704  movw     r3, #0x279
91811708  movt     r2, #0x9187
9181170C  ldr      r0, [sp, #8]
91811710  bl       #0x9184e684
91811714  mov      sl, #0
91811718  bl       #0x918107c4
9181171C  bl       #0x918107c4
91811720  mov      r2, sl
91811724  movw     r3, #0x8ee4
91811728  mov      r0, #0
9181172C  movt     r3, #0x9187
91811730  add      r1, sp, #0x1c
91811734  bl       #0x9185b080                ; 0x9185B080(r0=0, r1=&sp[0x1c], r2=0, r3=0x91878EE4)
91811738  subs     sl, r0, #0                 ; sl = 返回值，为 0 则跳 0x91811948
9181173C  beq      #0x91811948
91811740  ldr      fp, [sl, #4]               ; fp = [sl+4]
91811744  bl       #0x91867aa8
91811748  movw     r2, #0x51ec
9181174C  movw     r3, #0x51b8
91811750  movt     r2, #0x91b9
91811754  movt     r3, #0x91b9
91811758  mov      r1, r0
9181175C  mov      r0, fp
```

### 3. 传给 verify_sig 的四个参数

```asm
918118C0  ldr      r2, [sp, #0x10]
918118C4  cmp      r2, #0
918118C8  beq      #0x91811a38
918118CC  ldr      r3, [r2, #4]
918118D0  ldr      r3, [r3]
918118D4  ldr      sb, [r3, #4]
918118D8  ldr      r2, [sl, #0x10]            ; r2 = [sl+0x10]
918118DC  mov      r0, r6
918118E0  mov      r1, r7
918118E4  mov      r3, sb                     ; r3 = sb（分区名）
918118E8  ldr      r2, [r2, #8]               ; r2 = [r2+8]（签名指针）
918118EC  bl       #0x91810cb0                ; verify_sig(data, len, sig, name)
918118F0  subs     r8, r0, #0
918118F4  bne      #0x91811980
918118F8  ldr      r0, [sl, #4]
918118FC  bl       #0x9186e884
```

### 4. verify_sig：拼 DigestInfo + 算哈希 + 调比对

```asm
91810CB0  push     {r4, r5, r6, r7, r8, sb, sl, fp, lr}
91810CB4  movw     r5, #0x51ac
91810CB8  movt     r5, #0x91b9
91810CBC  sub      sp, sp, #0x3c
91810CC0  mov      ip, #1
91810CC4  mov      sb, r0                     ; sb = r0 = data
91810CC8  ldr      lr, [r5]
91810CCC  mov      r0, ip
91810CD0  mov      r8, r1                     ; ★ r8 = r1 = len（函数原参数）
91810CD4  mov      r1, #0x100
91810CD8  mov      r4, #0
91810CDC  strb     ip, [sp, #9]
91810CE0  str      r4, [sp, #0x10]
91810CE4  mov      fp, #0x31
91810CE8  str      lr, [sp, #0x34]
91810CEC  mov      sl, #0xd
91810CF0  mov      lr, #0x30
91810CF4  strb     ip, [sp, #0xe]
91810CF8  strb     lr, [sp]
91810CFC  mov      ip, #0x60
91810D00  strb     lr, [sp, #2]
91810D04  mov      r7, r2                     ; r7 = r2 = 签名
91810D08  mvn      lr, #0x79
91810D0C  mov      r2, #6
91810D10  strb     fp, [sp, #1]
91810D14  mov      r6, r3                     ; r6 = r3 = 分区名
91810D18  strb     sl, [sp, #3]
91810D1C  mov      r3, #9
91810D20  mov      sl, #0x65
91810D24  strb     r2, [sp, #4]
91810D28  strb     r3, [sp, #5]
91810D2C  mov      r2, #3
91810D30  mov      r3, #4
91810D34  strb     ip, [sp, #6]
91810D38  strb     lr, [sp, #7]
91810D3C  mov      ip, #5
91810D40  mov      lr, #0x20
91810D44  strb     sl, [sp, #0xa]
91810D48  strb     r3, [sp, #0xc]
91810D4C  mov      fp, #0x48
91810D50  strb     r3, [sp, #0x11]
91810D54  mov      r3, #2
91810D58  str      r4, [sp, #0x14]
91810D5C  str      r4, [sp, #0x18]
91810D60  str      r4, [sp, #0x1c]
91810D64  str      r4, [sp, #0x20]
91810D68  str      r4, [sp, #0x24]
91810D6C  str      r4, [sp, #0x28]
91810D70  str      r4, [sp, #0x2c]
91810D74  strh     r4, [sp, #0x30]
91810D78  strb     r4, [sp, #0x32]
91810D7C  strb     fp, [sp, #8]
91810D80  strb     r2, [sp, #0xb]
91810D84  strb     r3, [sp, #0xd]
91810D88  strb     ip, [sp, #0xf]
91810D8C  strb     lr, [sp, #0x12]
91810D90  bl       #0x9184fc2c
91810D94  subs     sl, r0, #0
91810D98  beq      #0x91810e28
91810D9C  mov      r0, sb
91810DA0  mov      r1, r8
91810DA4  mov      r2, #2
91810DA8  add      r3, sp, #0x13
91810DAC  bl       #0x918215b4                ; hash(data, len, algo=2, out=&sp[0x13])
91810DB0  mov      r0, r7
91810DB4  mov      r1, sl
91810DB8  mov      r2, r6
91810DBC  bl       #0x9182154c                ; 0x9182154C(sig, hash, name)
91810DC0  cmp      r0, #0x33
91810DC4  beq      #0x91810e0c
```

### 5. 0x9182154C：把分区名往下传

```asm
9182154C  push     {r4, lr}
91821550  movw     r4, #0x51ac
91821554  movt     r4, #0x91b9
91821558  sub      sp, sp, #0x10
9182155C  subs     r3, r2, #0                 ; r3 = r2 = 分区名
91821560  mov      r2, r1                     ; r2 = r1 = hash
91821564  ldr      ip, [r4]
91821568  str      ip, [sp, #0xc]
9182156C  beq      #0x9182159c
91821570  mov      r1, r0                     ; r1 = r0 = 签名
91821574  mov      ip, #1
91821578  mov      r0, #0x100                 ; r0 = 256（RSA 模数长度）
9182157C  str      ip, [sp]
91821580  bl       #0x9186cc54                ; 0x9186CC54(256, sig, hash, name, 1)
91821584  ldr      r2, [sp, #0xc]
91821588  ldr      r3, [r4]
9182158C  cmp      r2, r3
91821590  bne      #0x918215b0
91821594  add      sp, sp, #0x10
91821598  pop      {r4, pc}
9182159C  movw     r0, #0xc65c
```

### 6. ★ 0x9186CC54：出现对 [name+8] 的间接调用

```asm
9186CC54  push     {r4, r5, lr}
9186CC58  sub      sp, sp, #0x14
9186CC5C  movw     r4, #0x51ac
9186CC60  movt     r4, #0x91b9
9186CC64  ldr      ip, [r3, #8]               ; ip = [r3+8]  ← r3 = 分区名
9186CC68  ldr      r5, [sp, #0x20]
9186CC6C  ldr      lr, [r4]
9186CC70  str      r5, [sp]
9186CC74  ldr      ip, [ip, #8]               ; ip = [ip+8]
9186CC78  str      lr, [sp, #0xc]
9186CC7C  blx      ip                         ; ★ blx ip（间接调用）
9186CC80  ldr      r2, [sp, #0xc]
9186CC84  ldr      r3, [r4]
9186CC88  cmp      r2, r3
9186CC8C  bne      #0x9186cc98
9186CC90  add      sp, sp, #0x14
9186CC94  pop      {r4, r5, pc}
9186CC98  bl       #0x9184e70c
```

---

## 关键地址的静态数据

```
0x91880C08  hex: 2f73757276697661     u32: 0x7275732F  str: '/survival'
0x91880C14  hex: 2f626f6f74000000     u32: 0x6F6F622F  str: '/boot'
0x91B933A8  hex: 0000000000000000     u32: 0x00000000  str: ''
0x91B92D08  hex: 0000000000000000     u32: 0x00000000  str: ''
```

## 矛盾点

`0x91880C14` 处是裸字符串 `"/boot"`（7 字节，其后对齐为 `00 00 00`）。
若 `r3 = 0x91880C14`，则：

```
[r3+8] = [0x91880C1C] = 0x69766544   ; 即 ASCII "Devi"（"Device is tampered..." 的开头）
[0x69766544+8] = 访问 0x6976654C     ; 非法地址
```

设备能正常启动，说明这条路径不可能按字面执行。可能的解释：

1. `0x9182154C` 的入参在别处被重排，`r3` 实际不是分区名，而是一个描述符对象
2. 分区名字符串后面紧跟一个描述符结构，`+8` 落在这个结构内（但实测数据不支持）
3. `0x91811698: mov sb, r2` 之后 `sb` 被重新赋值（本摘录未覆盖全部指令）
4. `0x9186CC54` 存在多个入口，此处不是其常规入口
