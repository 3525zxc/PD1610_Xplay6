#include <stdio.h>
#include "../kernel/bootloop_monitor.c"

int main(int argc, char **argv)
{
    const char *out = argc > 1 ? argv[1] : "tests/blm_host_selftest.bin";
    FILE *f;

    blm_early_init(0x42000000ULL);
    blm_reserve_logmem();
    blm_mark(BLM_STAGE_START_KERNEL);
    blm_mark(BLM_STAGE_BEFORE_SETUP_ARCH);
    blm_mark(BLM_STAGE_SETUP_ARCH_ENTER);
    blm_mark(BLM_STAGE_FDT_SCAN_DONE);
    blm_mark(BLM_STAGE_PAGING_INIT);
    blm_mark(BLM_STAGE_AFTER_SETUP_ARCH);
    blm_mark(BLM_STAGE_CONSOLE_INIT);
    blm_mark(BLM_STAGE_REST_INIT);
    blm_mark(BLM_STAGE_KERNEL_INIT);
    blm_mark(BLM_STAGE_INITCALLS_DONE);
    blm_write_text("[1.112] arm-scmi arm-scmi.1.auto timed out in resp\n");
    blm_write_text("scmi_cpuss_telemetry_probe: Not able to find shared memory location\n");
    blm_mark(BLM_STAGE_PANIC_ENTER);
    blm_write_text("Kernel panic - not syncing: BLM selftest\n");

    f = fopen(out, "wb");
    if (!f) {
        fprintf(stderr, "WRITE_FAIL\n");
        return 1;
    }
    if (fwrite(blm_host_logmem, 1, BLM_LOG_SIZE, f) != BLM_LOG_SIZE) {
        fclose(f);
        fprintf(stderr, "SHORT_WRITE\n");
        return 1;
    }
    fclose(f);
    printf("HOST_SELFTEST_OK out=%s size=%u\n", out, (unsigned)BLM_LOG_SIZE);
    return 0;
}
