#ifndef BLM_LAYOUT_H
#define BLM_LAYOUT_H

#ifdef BLM_HOST_TEST
#include <stdint.h>
#include <stddef.h>
#else
#include <linux/types.h>
#endif

#define BLM_MAGIC 0x424C4D4C4F473031ULL
#define BLM_META_MAGIC 0x424C4D4D45544131ULL
#define BLM_STAGE_MAGIC 0x424D524BU
#define BLM_LINE_MAGIC 0x424C494EU
#define BLM_BUILD_TAG 0x50444D31U
#define BLM_STAGE_TEXT_TAG 0x424C4D53U
#define BLM_VERSION 1U

#define BLM_LOG_SIZE 0x40000U
#define BLM_FDT_LOG_OFFSET 0x100000ULL
#define BLM_FDT_WINDOW_SIZE 0x200000ULL
#define BLM_FDT_BASE_OFFSET 0x2000000ULL

#define BLM_META_SIZE 0x1000U
#define BLM_BANK_SIZE 0x1F000U
#define BLM_BANK0_OFF 0x1000U
#define BLM_BANK1_OFF 0x20000U

#define BLM_HEADER_SIZE 0x80U
#define BLM_STAGE_AREA_OFF 0x80U
#define BLM_STAGE_SLOT_SIZE 0x40U
#define BLM_STAGE_SLOTS 0x40U
#define BLM_LINE_AREA_OFF 0x1080U
#define BLM_LINE_SLOT_SIZE 0x100U
#define BLM_LINE_SLOTS 0x180U
#define BLM_USED_SIZE 0x19080U

#define BLM_H_MAGIC 0U
#define BLM_H_VERSION 8U
#define BLM_H_LOG_SIZE 12U
#define BLM_H_HEADER_SIZE 16U
#define BLM_H_STAGE_AREA_OFF 20U
#define BLM_H_STAGE_SLOT_SIZE 24U
#define BLM_H_STAGE_SLOTS 28U
#define BLM_H_LINE_AREA_OFF 32U
#define BLM_H_LINE_SLOT_SIZE 36U
#define BLM_H_LINE_SLOTS 40U
#define BLM_H_USED_SIZE 44U
#define BLM_H_FDT_PHYS 48U
#define BLM_H_LOG_PHYS 56U
#define BLM_H_LOG_OFFSET 64U
#define BLM_H_DDR_HINT 72U
#define BLM_H_GENERATION 80U
#define BLM_H_CRC 84U
#define BLM_H_BUILD_TAG 88U
#define BLM_H_CRC_LEN 84U

#define BLM_M_MAGIC 0U
#define BLM_M_GENERATION 8U
#define BLM_M_LAST_BANK 16U
#define BLM_M_CRC 20U
#define BLM_M_LAST_FDT 24U
#define BLM_M_LAST_LOG 32U
#define BLM_M_CRC_LEN 20U

#define BLM_S_MAGIC 0U
#define BLM_S_SEQ 4U
#define BLM_S_JIFFIES 8U
#define BLM_S_STAGE 16U
#define BLM_S_CPU 20U
#define BLM_S_CRC 24U
#define BLM_S_TEXT_TAG 28U
#define BLM_S_CRC_LEN 24U

#define BLM_L_MAGIC 0U
#define BLM_L_SEQ 4U
#define BLM_L_JIFFIES 8U
#define BLM_L_LENGTH 16U
#define BLM_L_CRC 20U
#define BLM_L_TEXT 24U
#define BLM_L_TEXT_LEN 232U
#define BLM_L_CRC_LEN 20U

#define BLM_STAGE_NONE 0U
#define BLM_STAGE_START_KERNEL 1U
#define BLM_STAGE_BEFORE_SETUP_ARCH 2U
#define BLM_STAGE_SETUP_ARCH_ENTER 3U
#define BLM_STAGE_FDT_SCAN_DONE 4U
#define BLM_STAGE_EARLY_IOREMAP 5U
#define BLM_STAGE_PAGING_INIT 6U
#define BLM_STAGE_UNFLATTEN_DT 7U
#define BLM_STAGE_AFTER_SETUP_ARCH 8U
#define BLM_STAGE_CONSOLE_INIT 9U
#define BLM_STAGE_CONSOLE_REGISTERED 10U
#define BLM_STAGE_REST_INIT 11U
#define BLM_STAGE_KERNEL_INIT 12U
#define BLM_STAGE_INITCALLS_DONE 13U
#define BLM_STAGE_ROOTFS_READY 14U
#define BLM_STAGE_USER_INIT_ATTEMPT 15U
#define BLM_STAGE_PANIC_ENTER 16U
#define BLM_STAGE_WATCHDOG_PANIC 17U
#define BLM_STAGE_BOOT_OK 18U
#define BLM_STAGE_MAX 18U

#if BLM_USED_SIZE > BLM_BANK_SIZE
#error BLM_USED_SIZE exceeds BLM_BANK_SIZE
#endif
#if (BLM_BANK1_OFF + BLM_BANK_SIZE) > BLM_LOG_SIZE
#error BLM bank 1 exceeds BLM_LOG_SIZE
#endif
#if BLM_FDT_LOG_OFFSET >= BLM_FDT_WINDOW_SIZE
#error BLM log offset is outside the mapped FDT 2 MiB window
#endif

static inline void blm_put_u32(uint8_t *p, uint32_t v)
{
    p[0] = (uint8_t)(v & 0xFFU);
    p[1] = (uint8_t)((v >> 8) & 0xFFU);
    p[2] = (uint8_t)((v >> 16) & 0xFFU);
    p[3] = (uint8_t)((v >> 24) & 0xFFU);
}

static inline void blm_put_u64(uint8_t *p, uint64_t v)
{
    uint32_t i;
    for (i = 0; i < 8; i++)
        p[i] = (uint8_t)((v >> (8 * i)) & 0xFFU);
}

static inline uint32_t blm_get_u32(const uint8_t *p)
{
    return (uint32_t)p[0] | ((uint32_t)p[1] << 8) |
           ((uint32_t)p[2] << 16) | ((uint32_t)p[3] << 24);
}

static inline uint64_t blm_get_u64(const uint8_t *p)
{
    uint64_t v = 0;
    uint32_t i;
    for (i = 0; i < 8; i++)
        v |= ((uint64_t)p[i]) << (8 * i);
    return v;
}

static inline uint32_t blm_crc32(const uint8_t *p, size_t n)
{
    uint32_t crc = 0xFFFFFFFFU;
    size_t i;
    uint32_t k;
    for (i = 0; i < n; i++) {
        crc ^= p[i];
        for (k = 0; k < 8; k++)
            crc = (crc >> 1) ^ (0xEDB88320U & (0U - (crc & 1U)));
    }
    return crc ^ 0xFFFFFFFFU;
}

static inline uint32_t blm_bank_offset(uint32_t bank)
{
    return (bank & 1U) ? BLM_BANK1_OFF : BLM_BANK0_OFF;
}

#endif
