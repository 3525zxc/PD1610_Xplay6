#ifndef _LINUX_BOOTLOOP_MONITOR_H
#define _LINUX_BOOTLOOP_MONITOR_H

#include <linux/types.h>
#include <linux/init.h>
#include <linux/blm_layout.h>

extern phys_addr_t __fdt_pointer __initdata;

void blm_early_init(phys_addr_t fdt_phys);
void blm_reserve_logmem(void);
void blm_mark(uint32_t stage);
void blm_write_bytes(const char *s, size_t n);
void blm_write_text(const char *s);
void blm_note_initcall(unsigned long fn);
void blm_trace_note(uint32_t id, const char *tag, unsigned long val);
void blm_arm_watchdog(void);
void blm_disarm_watchdog(void);

#endif
