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

/* System availability and process RSS are distinct, overlapping measurements. */
#define FLASH_SERVE_MAX_PROCESS_RSS_BYTES (UINT64_C(16) << 30)
#define FLASH_SERVE_RESOURCE_POLL_MS 250.0
static inline int flash_serve_process_rss_bytes(uint64_t *out) {
    if (!out) return 0;
    *out = 0;
#if defined(__APPLE__)
    mach_task_basic_info_data_t info;
    mach_msg_type_number_t count = MACH_TASK_BASIC_INFO_COUNT;
    if (task_info(mach_task_self(), MACH_TASK_BASIC_INFO,
                  (task_info_t)&info, &count) != KERN_SUCCESS) return 0;
    *out = info.resident_size;
    return 1;
#else
    return 0;
#endif
}

typedef struct {
    int active;
    int failure; /* 1 telemetry, 2 host reserve, 3 process RSS */
    double next_sample_ms;
} FlashServeResourceGuard;

static inline int flash_serve_guard_due(const FlashServeResourceGuard *g, double now) {
    return g->active && !g->failure && now >= g->next_sample_ms;
}
static inline void flash_serve_guard_begin(FlashServeResourceGuard *g, int enabled) {
    g->active = enabled;
    g->failure = 0;
    g->next_sample_ms = 0;
}
/* Latch failure until request replacement; never make a partial state reusable. */
static inline int flash_serve_guard_sample(FlashServeResourceGuard *g, double now,
                                          int host_ok, uint64_t available,
                                          int rss_ok, uint64_t rss) {
    if (!g->active) return 1;
    if (g->failure) return 0;
    if (!flash_serve_guard_due(g, now)) return 1;
    g->next_sample_ms = now + FLASH_SERVE_RESOURCE_POLL_MS;
    if (!host_ok || !rss_ok) g->failure = 1;
    else if (!flash_serve_host_reserve_admitted(available)) g->failure = 2;
    else if (rss >= FLASH_SERVE_MAX_PROCESS_RSS_BYTES) g->failure = 3;
    return !g->failure;
}
#endif
