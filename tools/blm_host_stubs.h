#ifndef BLM_HOST_STUBS_H
#define BLM_HOST_STUBS_H

#ifndef BLM_HOST_TEST
#define BLM_HOST_TEST
#endif
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include "blm_layout.h"

typedef uint64_t phys_addr_t;
typedef struct { uint32_t counter; } atomic_t;
#define ATOMIC_INIT(i) { (i) }
#define HZ 100U
#define __init
#define __initdata
#define __read_mostly

static uint64_t blm_host_jiffies_value;
#define jiffies blm_host_jiffies_value

struct timer_list {
    unsigned long expires;
    void (*function)(unsigned long);
    unsigned long data;
};

static uint8_t blm_host_logmem[BLM_LOG_SIZE];

static inline void *blm_host_phys_to_virt(uint64_t p)
{
    (void)p;
    return (void *)blm_host_logmem;
}

static inline void blm_host_flush(void *addr, size_t len)
{
    (void)addr;
    (void)len;
}

static inline void blm_host_reserve(uint64_t p, uint64_t s)
{
    (void)p;
    (void)s;
}

static inline void blm_host_panic(const char *fmt)
{
    (void)fmt;
}

static inline uint32_t atomic_inc_return(atomic_t *a)
{
    return ++a->counter;
}

static inline int mod_timer(struct timer_list *t, unsigned long expires)
{
    t->expires = expires;
    return 0;
}

static inline int del_timer(struct timer_list *t)
{
    (void)t;
    return 0;
}

#define setup_timer(t, fn, d) do { (t)->function = (fn); (t)->data = (d); } while (0)
#define panic(fmt, ...) blm_host_panic(fmt)
#define early_param(name, fn) static int (*blm_early_param_ref_##fn)(char *) __attribute__((unused)) = fn; static const char blm_early_param_name_##fn[] __attribute__((unused)) = name
#define BLM_PHYS_TO_VIRT(p) blm_host_phys_to_virt((uint64_t)(p))
#define BLM_FLUSH(a, l) blm_host_flush((a), (l))
#define BLM_RESERVE(p, s) blm_host_reserve((uint64_t)(p), (uint64_t)(s))

#endif
