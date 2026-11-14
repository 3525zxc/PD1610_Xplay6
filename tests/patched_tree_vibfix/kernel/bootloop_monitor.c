#ifdef BLM_HOST_TEST
#include "blm_host_stubs.h"
#include "blm_layout.h"
#else
#include <linux/kernel.h>
#include <linux/types.h>
#include <linux/string.h>
#include <linux/memblock.h>
#include <linux/console.h>
#include <linux/init.h>
#include <linux/jiffies.h>
#include <linux/timer.h>
#include <linux/atomic.h>
#include <asm/memory.h>
#include <asm/cacheflush.h>
#include <linux/bootloop_monitor.h>
#endif

#ifndef BLM_HOST_TEST
#define BLM_PHYS_TO_VIRT(p) phys_to_virt((phys_addr_t)(p))
#define BLM_FLUSH(a, l) __flush_dcache_area((a), (l))
#define BLM_RESERVE(p, s) memblock_reserve((phys_addr_t)(p), (phys_addr_t)(s))
#endif

/*
 * Line slots [0, BLM_TRACE_SLOTS) are reserved for fixed-position trace
 * milestones.  Ordinary printk/initcall lines only use the remaining slots,
 * so a panic register dump can never evict the last known good checkpoint.
 */
#define BLM_TRACE_SLOTS 32U
#define BLM_TRACE_SEQ_BASE 0xF0000000U

static uint8_t *blm_log_virt;
static uint8_t *blm_bank_virt;
static phys_addr_t blm_log_phys;
static int blm_ready;
static atomic_t blm_seq = ATOMIC_INIT(0);
static atomic_t blm_line_seq = ATOMIC_INIT(0);
static uint32_t blm_watchdog_secs;
static struct timer_list blm_watchdog_timer;

static void blm_line_write(const char *bytes, size_t len);
void blm_mark(uint32_t stage);
void blm_write_bytes(const char *s, size_t n);
void blm_write_text(const char *s);

static uint32_t blm_parse_u32(const char *s)
{
    uint32_t v = 0;
    while (*s >= '0' && *s <= '9') {
        v = v * 10U + (uint32_t)(*s - '0');
        s++;
    }
    return v;
}

static int __init blm_watchdog_setup(char *str)
{
    blm_watchdog_secs = blm_parse_u32(str);
    if (blm_watchdog_secs > 600U)
        blm_watchdog_secs = 600U;
    return 0;
}
early_param("blm_watchdog_secs", blm_watchdog_setup);

static int blm_meta_read(uint8_t *meta, uint64_t *gen, uint32_t *last_bank)
{
    if (blm_get_u64(meta + BLM_M_MAGIC) != BLM_META_MAGIC)
        return 0;
    if (blm_get_u32(meta + BLM_M_CRC) != blm_crc32(meta, BLM_M_CRC_LEN))
        return 0;
    *gen = blm_get_u64(meta + BLM_M_GENERATION);
    *last_bank = blm_get_u32(meta + BLM_M_LAST_BANK);
    return 1;
}

static void blm_meta_write(uint8_t *meta, uint64_t gen, uint32_t bank,
                           uint64_t fdt, uint64_t log)
{
    memset(meta, 0, BLM_META_SIZE);
    blm_put_u64(meta + BLM_M_MAGIC, BLM_META_MAGIC);
    blm_put_u64(meta + BLM_M_GENERATION, gen);
    blm_put_u32(meta + BLM_M_LAST_BANK, bank);
    blm_put_u64(meta + BLM_M_LAST_FDT, fdt);
    blm_put_u64(meta + BLM_M_LAST_LOG, log);
    blm_put_u32(meta + BLM_M_CRC, blm_crc32(meta, BLM_M_CRC_LEN));
    BLM_FLUSH(meta, BLM_META_SIZE);
}

static void blm_header_write(uint8_t *bank, uint64_t fdt, uint64_t log,
                             uint64_t ddr_hint, uint64_t gen)
{
    memset(bank, 0, BLM_HEADER_SIZE);
    blm_put_u64(bank + BLM_H_MAGIC, BLM_MAGIC);
    blm_put_u32(bank + BLM_H_VERSION, BLM_VERSION);
    blm_put_u32(bank + BLM_H_LOG_SIZE, BLM_LOG_SIZE);
    blm_put_u32(bank + BLM_H_HEADER_SIZE, BLM_HEADER_SIZE);
    blm_put_u32(bank + BLM_H_STAGE_AREA_OFF, BLM_STAGE_AREA_OFF);
    blm_put_u32(bank + BLM_H_STAGE_SLOT_SIZE, BLM_STAGE_SLOT_SIZE);
    blm_put_u32(bank + BLM_H_STAGE_SLOTS, BLM_STAGE_SLOTS);
    blm_put_u32(bank + BLM_H_LINE_AREA_OFF, BLM_LINE_AREA_OFF);
    blm_put_u32(bank + BLM_H_LINE_SLOT_SIZE, BLM_LINE_SLOT_SIZE);
    blm_put_u32(bank + BLM_H_LINE_SLOTS, BLM_LINE_SLOTS);
    blm_put_u32(bank + BLM_H_USED_SIZE, BLM_USED_SIZE);
    blm_put_u64(bank + BLM_H_FDT_PHYS, fdt);
    blm_put_u64(bank + BLM_H_LOG_PHYS, log);
    blm_put_u64(bank + BLM_H_LOG_OFFSET, BLM_FDT_LOG_OFFSET);
    blm_put_u64(bank + BLM_H_DDR_HINT, ddr_hint);
    blm_put_u32(bank + BLM_H_GENERATION, (uint32_t)gen);
    blm_put_u32(bank + BLM_H_CRC, blm_crc32(bank, BLM_H_CRC_LEN));
    blm_put_u32(bank + BLM_H_BUILD_TAG, BLM_BUILD_TAG);
    BLM_FLUSH(bank, BLM_HEADER_SIZE);
}

void blm_early_init(phys_addr_t fdt_phys)
{
    uint64_t gen = 1;
    uint64_t ddr_hint = 0;
    uint32_t bank_idx = 0;
    uint32_t last_bank = 0;
    uint8_t *meta;

    blm_log_phys = (phys_addr_t)((uint64_t)fdt_phys + BLM_FDT_LOG_OFFSET);
    blm_log_virt = (uint8_t *)BLM_PHYS_TO_VIRT(blm_log_phys);
    if (!blm_log_virt)
        return;

    meta = blm_log_virt;
    if (blm_meta_read(meta, &gen, &last_bank)) {
        gen += 1;
        bank_idx = (uint32_t)(gen & 1U);
    } else {
        gen = 1;
        bank_idx = 0;
    }
    if ((uint64_t)fdt_phys >= BLM_FDT_BASE_OFFSET)
        ddr_hint = (uint64_t)fdt_phys - BLM_FDT_BASE_OFFSET;

    blm_meta_write(meta, gen, bank_idx, (uint64_t)fdt_phys, (uint64_t)blm_log_phys);
    blm_bank_virt = blm_log_virt + blm_bank_offset(bank_idx);
    memset(blm_bank_virt, 0, BLM_BANK_SIZE);
    blm_header_write(blm_bank_virt, (uint64_t)fdt_phys, (uint64_t)blm_log_phys,
                     ddr_hint, gen);
    BLM_FLUSH(blm_bank_virt, BLM_BANK_SIZE);
    blm_ready = 1;
    blm_write_text("BLM monitor init\n");
}

void blm_reserve_logmem(void)
{
    if (!blm_ready)
        return;
    BLM_RESERVE(blm_log_phys, BLM_LOG_SIZE);
    blm_write_text("BLM memblock reserve\n");
}

void blm_mark(uint32_t stage)
{
    uint32_t seq;
    uint8_t *slot;

    if (!blm_ready || stage > BLM_STAGE_MAX || stage >= BLM_STAGE_SLOTS)
        return;
    seq = (uint32_t)atomic_inc_return(&blm_seq);
    slot = blm_bank_virt + BLM_STAGE_AREA_OFF + stage * BLM_STAGE_SLOT_SIZE;
    memset(slot, 0, BLM_STAGE_SLOT_SIZE);
    blm_put_u32(slot + BLM_S_MAGIC, BLM_STAGE_MAGIC);
    blm_put_u32(slot + BLM_S_SEQ, seq);
    blm_put_u64(slot + BLM_S_JIFFIES, (uint64_t)jiffies);
    blm_put_u32(slot + BLM_S_STAGE, stage);
    blm_put_u32(slot + BLM_S_CPU, 0);
    blm_put_u32(slot + BLM_S_TEXT_TAG, BLM_STAGE_TEXT_TAG);
    blm_put_u32(slot + BLM_S_CRC, blm_crc32(slot, BLM_S_CRC_LEN));
    BLM_FLUSH(slot, BLM_STAGE_SLOT_SIZE);
}

static void blm_line_write(const char *bytes, size_t len)
{
    uint32_t seq;
    uint32_t idx;
    uint8_t *slot;

    if (!blm_ready)
        return;
    if (len > BLM_L_TEXT_LEN)
        len = BLM_L_TEXT_LEN;
    seq = (uint32_t)atomic_inc_return(&blm_line_seq);
    idx = BLM_TRACE_SLOTS + (seq % (BLM_LINE_SLOTS - BLM_TRACE_SLOTS));
    slot = blm_bank_virt + BLM_LINE_AREA_OFF + idx * BLM_LINE_SLOT_SIZE;
    memset(slot, 0, BLM_LINE_SLOT_SIZE);
    blm_put_u32(slot + BLM_L_MAGIC, BLM_LINE_MAGIC);
    blm_put_u32(slot + BLM_L_SEQ, seq);
    blm_put_u64(slot + BLM_L_JIFFIES, (uint64_t)jiffies);
    blm_put_u32(slot + BLM_L_LENGTH, (uint32_t)len);
    memcpy(slot + BLM_L_TEXT, bytes, len);
    blm_put_u32(slot + BLM_L_CRC, blm_crc32(slot, BLM_L_CRC_LEN));
    BLM_FLUSH(slot, BLM_LINE_SLOT_SIZE);
}

static void blm_emit_line(const char *s, size_t len)
{
    while (len) {
        size_t n = len > BLM_L_TEXT_LEN ? BLM_L_TEXT_LEN : len;
        blm_line_write(s, n);
        s += n;
        len -= n;
    }
}

void blm_write_bytes(const char *s, size_t n)
{
    size_t start = 0;
    size_t i;

    if (!blm_ready || !s || !n)
        return;
    for (i = 0; i < n; i++) {
        if (s[i] == '\n') {
            if (i > start)
                blm_emit_line(s + start, i - start);
            start = i + 1;
        }
    }
    if (start < n)
        blm_emit_line(s + start, n - start);
}

void blm_write_text(const char *s)
{
    if (s)
        blm_write_bytes(s, strlen(s));
}

/*
 * Record every initcall entry as "IC <16 hex digits>\n" in the line ring.
 * The last IC entry of a failed boot is the initcall that never returned.
 * Hand-rolled hex encoding keeps this callable from printk/console context
 * without pulling in vsnprintf.
 */
void blm_note_initcall(unsigned long fn)
{
    static const char hex[] = "0123456789abcdef";
    char buf[24];
    int i;

    buf[0] = 'I';
    buf[1] = 'C';
    buf[2] = ' ';
    for (i = 0; i < 16; i++)
        buf[3 + i] = hex[(fn >> (60 - 4 * i)) & 0xfUL];
    buf[19] = '\n';
    buf[20] = 0;
    blm_write_text(buf);
}

/*
 * Fixed-position milestone: "TRC <tag> <16 hex>\n" in line slot <id>.
 * Its seq is forced above every ordinary line, so the host reader sorts it
 * last and a flood of printk can never evict it.
 */
void blm_trace_note(uint32_t id, const char *tag, unsigned long val)
{
    static const char hex[] = "0123456789abcdef";
    char buf[48];
    uint8_t *slot;
    uint32_t n = 0;
    uint32_t i;
    size_t tlen = 0;

    if (!blm_ready || id >= BLM_TRACE_SLOTS)
        return;
    buf[n++] = 'T';
    buf[n++] = 'R';
    buf[n++] = 'C';
    buf[n++] = ' ';
    if (tag) {
        while (tag[tlen] && tlen < 16U) {
            buf[n++] = tag[tlen];
            tlen++;
        }
    }
    buf[n++] = ' ';
    for (i = 0; i < 16; i++)
        buf[n++] = hex[(val >> (60 - 4 * i)) & 0xfUL];
    buf[n++] = '\n';

    slot = blm_bank_virt + BLM_LINE_AREA_OFF + id * BLM_LINE_SLOT_SIZE;
    memset(slot, 0, BLM_LINE_SLOT_SIZE);
    blm_put_u32(slot + BLM_L_MAGIC, BLM_LINE_MAGIC);
    blm_put_u32(slot + BLM_L_SEQ, BLM_TRACE_SEQ_BASE | id);
    blm_put_u64(slot + BLM_L_JIFFIES, (uint64_t)jiffies);
    blm_put_u32(slot + BLM_L_LENGTH, n);
    memcpy(slot + BLM_L_TEXT, buf, n);
    blm_put_u32(slot + BLM_L_CRC, blm_crc32(slot, BLM_L_CRC_LEN));
    BLM_FLUSH(slot, BLM_LINE_SLOT_SIZE);
}

static void blm_watchdog_fn(unsigned long data)
{
    (void)data;
    blm_mark(BLM_STAGE_WATCHDOG_PANIC);
    blm_trace_note(15, "WDT", (unsigned long)jiffies);
    blm_write_text("BLM watchdog timeout\n");
    panic("BLM watchdog timeout");
}

void blm_arm_watchdog(void)
{
    if (!blm_ready || !blm_watchdog_secs)
        return;
    setup_timer(&blm_watchdog_timer, blm_watchdog_fn, 0);
    mod_timer(&blm_watchdog_timer, jiffies + (uint64_t)blm_watchdog_secs * HZ);
    blm_write_text("BLM watchdog armed\n");
}

void blm_disarm_watchdog(void)
{
    if (blm_watchdog_secs)
        del_timer(&blm_watchdog_timer);
}

#ifndef BLM_HOST_TEST
static void blm_console_write(struct console *co, const char *s, unsigned int n)
{
    (void)co;
    blm_write_bytes(s, (size_t)n);
}

/*
 * 3.18 register_console() has a hard gate:
 *     if (!(newcon->flags & CON_ENABLED)) return;   (printk.c:2536)
 * A console whose name does not match a console= entry is therefore dropped
 * silently.  CON_ENABLED makes BLM a real sink; CON_ANYTIME keeps it alive
 * in panic / CPU-offline context; CON_PRINTBUFFER replays early printk.
 */
static struct console blm_console = {
    .name = "blm",
    .write = blm_console_write,
    .flags = CON_ENABLED | CON_ANYTIME | CON_PRINTBUFFER,
    .index = -1,
};

static int __init blm_console_init(void)
{
    register_console(&blm_console);
    blm_mark(BLM_STAGE_CONSOLE_REGISTERED);
    blm_write_text((blm_console.flags & CON_ENABLED)
                   ? "BLM console enabled\n" : "BLM console NOT enabled\n");
    return 0;
}
console_initcall(blm_console_init);
#endif
