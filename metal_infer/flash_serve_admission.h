#ifndef FLASH_SERVE_ADMISSION_H
#define FLASH_SERVE_ADMISSION_H
/*
 * Opt-in, default-preserving admission policy for the reviewed GPU-only envelope.
 * This does NOT replace the engine's own 65536-token allocation bound.
 * The helper is C-only for deterministic model-free tests.
 */
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#if defined(__APPLE__)
#include <mach/mach.h>
#include <mach/vm_statistics.h>
#endif

#define FLASH_SERVE_QUALIFIED_MAX_CONTEXT 32768
#define FLASH_SERVE_MIN_HOST_AVAILABLE_BYTES (UINT64_C(6) * 1024 * 1024 * 1024)

/* 0 = disabled, 1 = enabled, -1 = invalid explicit configuration. */
static inline int flash_serve_policy_mode(const char *value) {
    if (value == NULL) return 0;
    if (strcmp(value, "1") == 0) return 1;
    return -1;
}

/* Uses unsigned widened arithmetic and rejects negative, overflow and all excess. */
static inline int flash_serve_context_admitted(int current, int input, int generation,
                                                int engine_cap, int gpu_cap) {
    if (current < 0 || input < 0 || generation < 0 || engine_cap <= 0 || gpu_cap <= 0)
        return 0;
    uint64_t required = (uint64_t)current + (uint64_t)input + (uint64_t)generation;
    uint64_t limit = FLASH_SERVE_QUALIFIED_MAX_CONTEXT;
    if ((uint64_t)engine_cap < limit) limit = (uint64_t)engine_cap;
    if ((uint64_t)gpu_cap < limit) limit = (uint64_t)gpu_cap;
    return required <= limit;
}

static inline int flash_serve_host_reserve_admitted(uint64_t available_bytes) {
    return available_bytes >= FLASH_SERVE_MIN_HOST_AVAILABLE_BYTES;
}

/* Conservative observed host free + inactive pages. Fail closed if unavailable.
 * This is a request-time admission sample, NOT continuous memory enforcement.
 */
static inline int flash_serve_host_available_bytes(uint64_t *out) {
    if (!out) return 0;
    *out = 0;
#if defined(__APPLE__)
    vm_statistics64_data_t stats;
    mach_msg_type_number_t count = HOST_VM_INFO64_COUNT;
    mach_port_t host = mach_host_self();
    kern_return_t kr = host_statistics64(host, HOST_VM_INFO64, (host_info64_t)&stats, &count);
    vm_size_t page_size = 0;
    kern_return_t page_kr = host_page_size(host, &page_size);
    mach_port_deallocate(mach_task_self(), host);
    if (kr != KERN_SUCCESS || page_kr != KERN_SUCCESS || page_size == 0)
        return 0;
    *out = ((uint64_t)stats.free_count + (uint64_t)stats.inactive_count) * (uint64_t)page_size;
    return 1;
#else
    return 0;
#endif
}
#endif
