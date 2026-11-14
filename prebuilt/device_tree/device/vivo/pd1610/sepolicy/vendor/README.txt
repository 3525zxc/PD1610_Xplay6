PD1610 的 vendor sepolicy 补丁目录（当前为空）。

首版依赖 androidboot.selinux=permissive 启动，先收集 denial 再补规则：
    adb shell dmesg | grep avc
    adb shell cat /proc/kmsg 2>/dev/null | grep avc
补齐流程：把 denials 里的 scontext/tcontext/tclass 整理成 allow 规则放进本目录，
写好后去掉 BoardConfig.mk 里 BOARD_KERNEL_CMDLINE 末尾的
androidboot.selinux=permissive，重新打包验证。
