/*
 * FlashMoEEngine.m — iOS wrapper for the Flash-MoE inference engine
 *
 * Unity build: includes infer.m directly (with CHAT_MODE to suppress main()).
 * Provides the C API defined in FlashMoEEngine.h for Swift/SwiftUI integration.
 *
 * Single-instance design: iOS memory constraints mean only one model at a time.
 * The FlashMoEContext struct holds all state, wrapping infer.m's static globals.
 */

#define CHAT_MODE 1  // suppress main() in infer.m

// Unity build — include the entire inference engine
// This gives us access to all static functions and globals
#include "../EngineSources/infer.m"

#include "FlashMoEEngine.h"
#include <stdatomic.h>
#include <os/proc.h>

// ============================================================================
// FlashMoEContext — wraps engine state for the public C API
// ============================================================================

struct FlashMoEContext {
    // Lifecycle state
    int loaded;                    // 1 if a model is loaded
    atomic_int cancelled;          // 1 if generation should stop

    // Model resources (owned)
    WeightFile *wf;
    Vocabulary *vocab;
    int *layer_fds;                // [num_layers] file descriptors for expert layers
    int *layer_fds_cold_local;     // [num_layers] cold file descriptors
    void **layer_mmaps;            // [num_layers] mmap'd expert data
    size_t *layer_mmap_sizes;      // [num_layers] mmap sizes
    void **layer_states;           // [num_layers] linear attention state
    KVCache **kv_caches;           // [num_layers] KV caches for full attention
    float *hidden;                 // [hidden_dim] working buffer
    float *logits;                 // [vocab_size] logits buffer
    uint16_t *final_norm_w;        // pointer into wf (not owned)
    int K;                         // num experts per token

    // Conversation state (for KV cache reuse)
    int current_pos;               // sequence position for RoPE (persists across turns)
    int turn_count;                // 0 = fresh session, >0 = has history

    // Generation stats
    double tokens_per_second;
    int tokens_generated;
    double total_time_ms;
    double ttft_ms;

    // Error state
    char last_error[512];
};

// Stable storage for the model path. Swift passes a borrowed UTF-8 pointer into
// flashmoe_load(); copy it immediately so tokenizer/stats globals never retain
// a pointer whose Swift/NSString lifetime has ended.
static char g_flashmoe_model_path[1024];

// ============================================================================
// Shader loading for iOS — find shaders.metal in the app bundle
// ============================================================================

// Override the shader search path for iOS: look in the app bundle first
static NSString *flashmoe_find_shader_source(void) {
    NSError *error = nil;
    NSString *src = nil;

    // 1. Try app bundle (iOS deployment)
    NSString *bundlePath = [[NSBundle mainBundle] pathForResource:@"shaders" ofType:@"metal"];
    if (bundlePath) {
        src = [NSString stringWithContentsOfFile:bundlePath encoding:NSUTF8StringEncoding error:&error];
        if (src) return src;
    }

    // 2. Try relative paths (macOS development / testing)
    NSArray *paths = @[@"shaders.metal", @"metal_infer/shaders.metal"];
    for (NSString *p in paths) {
        src = [NSString stringWithContentsOfFile:p encoding:NSUTF8StringEncoding error:&error];
        if (src) return src;
    }

    return nil;
}

// ============================================================================
// tokenize_continuation_turn — local copy for iOS
// (The original is inside #ifndef CHAT_MODE in infer.m, excluded by our #define)
// ============================================================================

static PromptTokens *flashmoe_tokenize_continuation_turn(const char *user_content) {
    const char *prefix = "\n<|im_start|>user\n";
    const char *suffix = "<|im_end|>\n<|im_start|>assistant\n";

    size_t prompt_len = strlen(prefix) + strlen(user_content) + strlen(suffix) + 1;
    char *prompt = malloc(prompt_len);
    if (!prompt) return NULL;
    snprintf(prompt, prompt_len, "%s%s%s", prefix, user_content, suffix);
    PromptTokens *pt = encode_prompt_text_to_tokens(prompt);
    free(prompt);
    return pt;
}

// ============================================================================
// Load validation / cleanup helpers
// ============================================================================

static int flashmoe_readable_nonempty_file(const char *path) {
    struct stat st;
    return path && access(path, R_OK) == 0 &&
           stat(path, &st) == 0 && S_ISREG(st.st_mode) && st.st_size > 0;
}

static int flashmoe_validate_selected_package(const char *model_path,
                                              const char *expert_dir,
                                              int require_tiered_manifest,
                                              char *error_buf,
                                              size_t error_buf_size) {
    const char *required_files[] = {
        "config.json", "model_weights.json", "model_weights.bin",
        "vocab.bin", "tokenizer.bin", NULL
    };
    char path[1024];
    for (int i = 0; required_files[i]; i++) {
        snprintf(path, sizeof(path), "%s/%s", model_path, required_files[i]);
        if (!flashmoe_readable_nonempty_file(path)) {
            snprintf(error_buf, error_buf_size, "Missing or empty required model file: %s",
                     required_files[i]);
            return 0;
        }
    }
    if (require_tiered_manifest) {
        snprintf(path, sizeof(path), "%s/%s/tiered_manifest.json", model_path, expert_dir);
        if (!flashmoe_readable_nonempty_file(path)) {
            snprintf(error_buf, error_buf_size,
                     "Missing or empty tiered manifest: %s/tiered_manifest.json", expert_dir);
            return 0;
        }
    }
    for (int layer = 0; layer < g_cfg.num_layers; layer++) {
        snprintf(path, sizeof(path), "%s/%s/layer_%02d.bin",
                 model_path, expert_dir, layer);
        if (!flashmoe_readable_nonempty_file(path)) {
            snprintf(error_buf, error_buf_size,
                     "Missing or empty expert layer %d: %s/layer_%02d.bin",
                     layer, expert_dir, layer);
            return 0;
        }
    }
    return 1;
}

static int flashmoe_load_fail(FlashMoEContext *ctx, const char *message) {
    if (ctx && message && message[0]) {
        snprintf(ctx->last_error, sizeof(ctx->last_error), "%s", message);
    }
    if (ctx) flashmoe_unload(ctx);
    return -1;
}

// ============================================================================
// Public API Implementation
// ============================================================================

FlashMoEContext *flashmoe_create(void) {
    FlashMoEContext *ctx = calloc(1, sizeof(FlashMoEContext));
    if (!ctx) return NULL;
    ctx->loaded = 0;
    atomic_store(&ctx->cancelled, 0);
    ctx->last_error[0] = '\0';
    return ctx;
}

int flashmoe_load(FlashMoEContext *ctx, const FlashMoEConfig *config) {
    if (!ctx || !config || !config->model_path) {
        if (ctx) snprintf(ctx->last_error, sizeof(ctx->last_error), "Invalid arguments");
        return -1;
    }

    // This wrapper currently chooses the "clean unloaded on failure" form of
    // transactional replacement. The previous model is released first; every
    // subsequent failure path unwinds all resources acquired by the new load.
    if (ctx->loaded) {
        flashmoe_unload(ctx);
    }
    ctx->last_error[0] = '\0';

    @autoreleasepool {
        if (strlcpy(g_flashmoe_model_path, config->model_path,
                    sizeof(g_flashmoe_model_path)) >= sizeof(g_flashmoe_model_path)) {
            return flashmoe_load_fail(ctx, "Model path is too long");
        }
        const char *model_path = g_flashmoe_model_path;

        // ---- Load model configuration ----
        config_init_defaults();

        // Set model path for tokenizer lookup
        g_model_path_for_tokenizer = model_path;

        // Build manifest path for config loading
        char manifest_path_buf[1024];
        snprintf(manifest_path_buf, sizeof(manifest_path_buf), "%s/model_weights.json", model_path);

        load_config_from_config_json(model_path);
        if (access(manifest_path_buf, R_OK) == 0) {
            load_config_from_manifest(manifest_path_buf);
        }
        if (!validate_target_architecture()) {
            return flashmoe_load_fail(ctx,
                                      "Unsupported model architecture or configuration");
        }

        // Note: MAX_SEQ_LEN is a compile-time constant in infer.m.
        // KV caches are allocated at MAX_SEQ_LEN. On iOS, context is
        // effectively limited by available memory and max_tokens passed
        // to flashmoe_generate(). No runtime capping needed here.
        // Suppress debug output for iOS
        g_stream_mode = 1;

        if (config->think_budget > 0) {
            g_think_budget = config->think_budget;
        }

        // Set quantization mode
        g_use_tiered = config->use_tiered;
        g_use_2bit = config->use_2bit;

        // Set cache I/O split (fanout mode): >1 = split expert preads into N chunks
        if (config->cache_io_split > 1) {
            g_cache_io_split = config->cache_io_split;
        } else {
            g_cache_io_split = 1;  // disabled by default
        }

        // KV cache sizing — allocate only what we need
        {
            int default_ctx = 8192;
#if TARGET_OS_IOS
            if (![[NSProcessInfo processInfo] isMacCatalystApp]) {
                default_ctx = 2048;  // iPhone: conserve memory
            }
#endif
            int ctx_limit = (config->max_context > 0) ? config->max_context : default_ctx;
            if (ctx_limit > MAX_SEQ_LEN) ctx_limit = MAX_SEQ_LEN;
            g_kv_seq_len = ctx_limit;
            size_t kv_per_cache = (size_t)ctx_limit * g_cfg.num_kv_heads * g_cfg.head_dim * sizeof(float);
            NSLog(@"[FlashMoE] KV cache: %d positions (%.1f MB per cache x %d layers)",
                  ctx_limit, kv_per_cache / 1e6, g_cfg.num_full_attn_layers);
        }

        // K = experts per token from config (capped to MAX_K)
        ctx->K = g_cfg.num_experts_per_tok;
        if (ctx->K > MAX_K) ctx->K = MAX_K;

        // ---- Build file paths ----
        char weights_path[1024], manifest_path[1024], vocab_path[1024];

        // On iOS, weight files are in the model directory
        snprintf(weights_path, sizeof(weights_path), "%s/model_weights.bin", model_path);
        snprintf(manifest_path, sizeof(manifest_path), "%s/model_weights.json", model_path);

        // Vocab/tokenizer: try model dir first, then app bundle
        snprintf(vocab_path, sizeof(vocab_path), "%s/vocab.bin", model_path);
        if (access(vocab_path, R_OK) != 0) {
            // Try app bundle
            NSString *bundleVocab = [[NSBundle mainBundle] pathForResource:@"vocab" ofType:@"bin"];
            if (bundleVocab) {
                strlcpy(vocab_path, [bundleVocab UTF8String], sizeof(vocab_path));
            }
        }

        // ---- Resolve expert package before allocating Metal resources ----
        if (!g_use_2bit && !g_use_tiered) {
            char probe[1024];
            snprintf(probe, sizeof(probe),
                     "%s/packed_experts_tiered/tiered_manifest.json", model_path);
            if (access(probe, R_OK) == 0 && load_tiered_manifest(model_path)) {
                g_use_tiered = 1;
            }
        }
        if (g_use_tiered && !g_tiered_manifest) {
            if (!load_tiered_manifest(model_path)) {
                return flashmoe_load_fail(ctx,
                                          "Tiered mode requested but no valid manifest found");
            }
        }

        const char *expert_dir = g_use_tiered ? "packed_experts_tiered" :
                                 g_use_2bit ? "packed_experts_2bit" :
                                             "packed_experts";
        char package_error[512] = {0};
        if (!flashmoe_validate_selected_package(model_path, expert_dir,
                                                g_use_tiered,
                                                package_error,
                                                sizeof(package_error))) {
            return flashmoe_load_fail(ctx, package_error);
        }

        // ---- Initialize Metal ----
        g_metal = metal_setup();
        if (!g_metal) {
            return flashmoe_load_fail(ctx, "Metal initialization failed");
        }

        // ---- Initialize I/O thread pool ----
        if (!io_pool_init()) {
            return flashmoe_load_fail(ctx, "I/O thread pool initialization failed");
        }

        // ---- Load weights ----
        ctx->wf = open_weights(weights_path, manifest_path);
        if (!ctx->wf) {
            char error[512];
            snprintf(error, sizeof(error), "Failed to load weights from %s", weights_path);
            return flashmoe_load_fail(ctx, error);
        }
        if (!validate_native_tensor_layout(ctx->wf)) {
            return flashmoe_load_fail(ctx, "Model tensor layout/dtype validation failed");
        }

        // Wrap weight file for Metal GPU access
        metal_set_weights(g_metal, ctx->wf->data, ctx->wf->size);

        // ---- Load vocabulary ----
        ctx->vocab = load_vocab(vocab_path);
        if (!ctx->vocab) {
            char error[512];
            snprintf(error, sizeof(error), "Failed to load vocabulary from %s", vocab_path);
            return flashmoe_load_fail(ctx, error);
        }

        // ---- Initialize tokenizer ----
        init_tokenizer();

        // ---- Open packed expert files ----
        // Initialize each table immediately after allocation so partial-load
        // cleanup never interprets uninitialized descriptor/map entries.
        ctx->layer_fds = malloc((size_t)g_cfg.num_layers * sizeof(int));
        if (!ctx->layer_fds)
            return flashmoe_load_fail(ctx, "Expert fd table allocation failed");
        for (int i = 0; i < g_cfg.num_layers; i++) ctx->layer_fds[i] = -1;

        ctx->layer_fds_cold_local = malloc((size_t)g_cfg.num_layers * sizeof(int));
        if (!ctx->layer_fds_cold_local)
            return flashmoe_load_fail(ctx, "Cold expert fd table allocation failed");
        for (int i = 0; i < g_cfg.num_layers; i++) ctx->layer_fds_cold_local[i] = -1;

        ctx->layer_mmaps = malloc((size_t)g_cfg.num_layers * sizeof(void *));
        if (!ctx->layer_mmaps)
            return flashmoe_load_fail(ctx, "Expert mmap table allocation failed");
        for (int i = 0; i < g_cfg.num_layers; i++) ctx->layer_mmaps[i] = MAP_FAILED;

        ctx->layer_mmap_sizes = calloc((size_t)g_cfg.num_layers, sizeof(size_t));
        if (!ctx->layer_mmap_sizes)
            return flashmoe_load_fail(ctx, "Expert mmap-size table allocation failed");

        memset(g_expert_seen, 0, sizeof(g_expert_seen));
        // Initialize per-layer quant arrays to match the global mode
        // (CLI main() does this during fd open; iOS must do it explicitly)
        memset(g_layer_is_2bit, 0, sizeof(g_layer_is_2bit));
        memset(g_layer_is_q3_hybrid, 0, sizeof(g_layer_is_q3_hybrid));
        memset(g_layer_is_q3_outlier, 0, sizeof(g_layer_is_q3_outlier));

        for (int i = 0; i < g_cfg.num_layers; i++) {
            char path[1024];
            snprintf(path, sizeof(path), "%s/%s/layer_%02d.bin",
                     model_path, expert_dir, i);
            ctx->layer_fds[i] = open(path, O_RDONLY);
            if (ctx->layer_fds[i] < 0) {
                char error[512];
                snprintf(error, sizeof(error), "Failed to open expert layer %d: %s", i, path);
                return flashmoe_load_fail(ctx, error);
            }
            // Set per-layer quant flag so fused_layer_forward uses correct expert size
            if (g_use_2bit) g_layer_is_2bit[i] = 1;
            fcntl(ctx->layer_fds[i], F_RDAHEAD, 0);
            struct stat st;
            if (fstat(ctx->layer_fds[i], &st) != 0 || st.st_size <= 0) {
                char error[512];
                snprintf(error, sizeof(error), "Invalid expert layer %d: %s", i, path);
                return flashmoe_load_fail(ctx, error);
            }
            ctx->layer_mmap_sizes[i] = st.st_size;
                    // Skip mmap on real iOS devices — 60 × 1.9 GB = 112 GB
                    // of mmap'd expert data causes jetsam kills.
                    // macOS (including "Designed for iPad") has plenty of address space.
                    int is_real_ios = 0;
#if TARGET_OS_IOS
                    // Runtime check: ProcessInfo.processInfo.isMacCatalystApp is false
                    // on real iOS devices but true on Mac running iPad app
                    is_real_ios = ![[NSProcessInfo processInfo] isMacCatalystApp];
#endif
            if (!is_real_ios) {
                ctx->layer_mmaps[i] = mmap(NULL, st.st_size, PROT_READ, MAP_PRIVATE,
                                           ctx->layer_fds[i], 0);
                // mmap is an optimization only; pread remains the safe fallback.
            }
        }

        // Log expert I/O mode
        {
            int mmap_count = 0;
            for (int i = 0; i < g_cfg.num_layers; i++) {
                if (ctx->layer_mmaps[i] != MAP_FAILED) mmap_count++;
            }
            NSLog(@"[experts] %d/%d layers opened, %d mmap'd, %d pread-only",
                  g_cfg.num_layers, g_cfg.num_layers, mmap_count, g_cfg.num_layers - mmap_count);
        }

        // Wire up global cold fds
        g_layer_fds_cold = ctx->layer_fds_cold_local;

        // ---- Deferred expert state ----
        // g_deferred.h_mid is now a static array [MAX_HIDDEN_DIM] — no allocation needed
        memset(g_deferred.h_mid, 0, sizeof(g_deferred.h_mid));

        // ---- Allocate per-layer state ----
        ctx->layer_states = calloc((size_t)g_cfg.num_layers, sizeof(void *));
        ctx->kv_caches = calloc((size_t)g_cfg.num_layers, sizeof(KVCache *));
        if (!ctx->layer_states || !ctx->kv_caches) {
            return flashmoe_load_fail(ctx, "Per-layer state table allocation failed");
        }

        for (int i = 0; i < g_cfg.num_layers; i++) {
            if (((i + 1) % FULL_ATTN_INTERVAL == 0)) {
                ctx->kv_caches[i] = kv_cache_new();
                if (!ctx->kv_caches[i] || !ctx->kv_caches[i]->k_cache || !ctx->kv_caches[i]->v_cache) {
                    snprintf(ctx->last_error, sizeof(ctx->last_error),
                             "KV cache alloc failed at layer %d (seq=%d, need %.0f MB per cache). "
                             "Try reducing max context or free device memory.",
                             i, g_kv_seq_len,
                             (double)g_kv_seq_len * NUM_KV_HEADS * HEAD_DIM * sizeof(float) / 1e6);
                    NSLog(@"[FlashMoE] %s", ctx->last_error);
                    char error[512];
                    strlcpy(error, ctx->last_error, sizeof(error));
                    return flashmoe_load_fail(ctx, error);
                }
            } else {
                ctx->layer_states[i] = linear_attn_state_new();
                if (!ctx->layer_states[i]) {
                    char error[256];
                    snprintf(error, sizeof(error),
                             "Linear attention state allocation failed at layer %d", i);
                    return flashmoe_load_fail(ctx, error);
                }
            }
        }

        // ---- Allocate working buffers ----
        ctx->hidden = calloc((size_t)HIDDEN_DIM, sizeof(float));
        ctx->logits = calloc((size_t)VOCAB_SIZE, sizeof(float));
        ctx->final_norm_w = get_tensor_ptr(ctx->wf, "model.norm.weight");
        if (!ctx->hidden || !ctx->logits || !ctx->final_norm_w) {
            return flashmoe_load_fail(ctx, "Working-buffer or final-norm allocation failed");
        }

        // ---- Build layer cache (precomputes weight pointers) ----
        build_layer_cache(ctx->wf);

        ctx->loaded = 1;
        if (config->verbose) {
            NSLog(@"[FlashMoE] Model loaded: %d layers, %d experts (K=%d), hidden=%d",
                  g_cfg.num_layers, g_cfg.num_experts, ctx->K, HIDDEN_DIM);
        }

        return 0;
    }
}

void flashmoe_unload(FlashMoEContext *ctx) {
    if (!ctx) return;

    @autoreleasepool {
        // Wait for any in-flight GPU work
        if (g_deferred.active) {
            [g_deferred.cmd_experts waitUntilCompleted];
            g_deferred.active = 0;
            g_deferred.cmd_experts = nil;
        }

        // Reset async pread state
        g_async_pread.active = 0;

        // Shutdown I/O pool
        io_pool_shutdown();

        // Close expert files
        if (ctx->layer_fds) {
            for (int i = 0; i < g_cfg.num_layers; i++) {
                if (ctx->layer_mmaps && ctx->layer_mmaps[i] != MAP_FAILED)
                    munmap(ctx->layer_mmaps[i], ctx->layer_mmap_sizes[i]);
                if (ctx->layer_fds[i] >= 0)
                    close(ctx->layer_fds[i]);
                if (ctx->layer_fds_cold_local && ctx->layer_fds_cold_local[i] >= 0)
                    close(ctx->layer_fds_cold_local[i]);
            }
            free(ctx->layer_fds); ctx->layer_fds = NULL;
            free(ctx->layer_fds_cold_local); ctx->layer_fds_cold_local = NULL;
            free(ctx->layer_mmaps); ctx->layer_mmaps = NULL;
            free(ctx->layer_mmap_sizes); ctx->layer_mmap_sizes = NULL;
        }

        // Free per-layer state. These tables may be only partially allocated
        // when a load fails, so clean them independently.
        if (ctx->kv_caches) {
            for (int i = 0; i < g_cfg.num_layers; i++) {
                if (ctx->kv_caches[i]) kv_cache_free(ctx->kv_caches[i]);
            }
            free(ctx->kv_caches); ctx->kv_caches = NULL;
        }
        if (ctx->layer_states) {
            for (int i = 0; i < g_cfg.num_layers; i++) {
                if (ctx->layer_states[i]) linear_attn_state_free(ctx->layer_states[i]);
            }
            free(ctx->layer_states); ctx->layer_states = NULL;
        }

        // Free working buffers
        free(ctx->hidden); ctx->hidden = NULL;
        free(ctx->logits); ctx->logits = NULL;

        // Reset deferred state (h_mid is now a static array, no free needed)
        memset(g_deferred.h_mid, 0, sizeof(g_deferred.h_mid));

        // Free weight file (munmap + manifest)
        if (ctx->wf) {
            if (ctx->wf->data) munmap(ctx->wf->data, ctx->wf->size);
            if (ctx->wf->manifest) {
                free(ctx->wf->manifest->tensors);
                free(ctx->wf->manifest);
            }
            free(ctx->wf);
            ctx->wf = NULL;
        }
        ctx->final_norm_w = NULL;

        // Reset tensor hash table (points into freed manifest)
        memset(tensor_ht, 0, sizeof(tensor_ht));
        tensor_ht_built = 0;

        // Free vocabulary
        if (ctx->vocab) {
            free(ctx->vocab);
            ctx->vocab = NULL;
        }

        // Reset static tracking arrays (no longer dynamically allocated)
        memset(g_expert_freq, 0, sizeof(g_expert_freq));
        memset(g_expert_seen, 0, sizeof(g_expert_seen));
        memset(g_cache_seen, 0, sizeof(g_cache_seen));
        memset(g_cache_last_touch_token, 0, sizeof(g_cache_last_touch_token));
        memset(g_cache_last_evict_token, 0, sizeof(g_cache_last_evict_token));
        memset(g_pred_experts, 0, sizeof(g_pred_experts));
        memset(g_pred_count, 0, sizeof(g_pred_count));

        // Reset layer cache so it rebuilds on next load
        memset(layer_cache, 0, sizeof(layer_cache));
        layer_cache_built = 0;

        // Free tiered manifest
        if (g_tiered_manifest) {
            free(g_tiered_manifest);
            g_tiered_manifest = NULL;
            g_use_tiered = 0;
        }

        // Reset KV cache limit
        g_kv_seq_len = MAX_SEQ_LEN;

        // Reset prediction state
        g_pred_enabled = 0;
        g_pred_generating = 0;
        g_pred_valid = 0;
        g_pred_hits = 0;
        g_pred_misses = 0;
        g_pred_layers = 0;

        // Reset global flags for clean reload
        g_freq_tracking = 0;
        g_cache_telemetry_enabled = 0;

        // Release Metal context
        // MetalCtx is calloc'd but holds ARC __strong id<> objects.
        // free() alone does NOT trigger ARC release — we must nil each
        // id<> member so ARC decrements refcounts before we free the struct.
        if (g_metal) {
            // Core objects
            g_metal->device = nil;
            g_metal->queue = nil;
            g_metal->library = nil;
            // Pipeline states
            g_metal->matvec_v3 = nil;
            g_metal->matvec_v5 = nil;
            g_metal->matvec_fast = nil;
            g_metal->matvec_2bit = nil;
            g_metal->matvec_iq3_xxs = nil;
            g_metal->matvec_iq4_xs = nil;
            g_metal->matvec_q5_k = nil;
            g_metal->matvec_q8_0 = nil;
            g_metal->matvec_q6_k = nil;
            // NAX
            g_metal->nax_library = nil;
            g_metal->nax_dequant = nil;
            g_metal->nax_f32_to_half = nil;
            g_metal->nax_gemm = nil;
            g_metal->nax_extract = nil;
            g_metal->nax_w_half = nil;
            g_metal->nax_x_half = nil;
            g_metal->nax_c_buf = nil;
            // Norm/activation pipelines
            g_metal->rms_norm_sum = nil;
            g_metal->rms_norm_apply = nil;
            g_metal->rms_norm_apply_bf16 = nil;
            g_metal->residual_add = nil;
            g_metal->swiglu = nil;
            // GPU attention pipelines
            g_metal->attn_scores_pipe = nil;
            g_metal->attn_softmax_pipe = nil;
            g_metal->attn_values_pipe = nil;
            g_metal->sigmoid_gate_pipe = nil;
            // MoE combine
            g_metal->moe_combine_residual = nil;
            // Delta-net pipelines
            g_metal->delta_net_step = nil;
            g_metal->conv1d_step = nil;
            g_metal->rms_norm_qk = nil;
            g_metal->compute_decay_beta = nil;
            g_metal->gated_rms_norm = nil;
            // Reusable buffers
            g_metal->buf_input = nil;
            g_metal->buf_output = nil;
            g_metal->wf_buf = nil;
            g_metal->gguf_qkv_buf = nil;
            g_metal->gguf_full_attn_buf = nil;
            g_metal->gguf_linear_buf = nil;
            g_metal->gguf_shared_buf = nil;
            g_metal->gguf_lm_head_buf = nil;
            for (int i = 0; i < MAX_BATCH_SLOTS; i++)
                g_metal->batch_out[i] = nil;
            // Legacy single-expert buffers
            g_metal->buf_expert_data = nil;
            g_metal->buf_expert_input = nil;
            g_metal->buf_expert_gate = nil;
            g_metal->buf_expert_up = nil;
            g_metal->buf_expert_act = nil;
            g_metal->buf_expert_out = nil;
            // Multi-expert buffers
            g_metal->buf_multi_expert_input = nil;
            for (int k = 0; k < MAX_K; k++) {
                g_metal->buf_multi_expert_data[k] = nil;
                g_metal->buf_multi_expert_data_B[k] = nil;
                g_metal->buf_multi_expert_gate[k] = nil;
                g_metal->buf_multi_expert_up[k] = nil;
                g_metal->buf_multi_expert_act[k] = nil;
                g_metal->buf_multi_expert_out[k] = nil;
            }
            // Shared expert buffers
            g_metal->buf_shared_gate = nil;
            g_metal->buf_shared_up = nil;
            g_metal->buf_shared_act = nil;
            g_metal->buf_shared_out = nil;
            // Fused o_proj+norm+routing buffers
            g_metal->buf_residual = nil;
            g_metal->buf_h_mid = nil;
            g_metal->buf_sum_sq = nil;
            // GPU attention buffers
            for (int i = 0; i < 16; i++) {
                g_metal->buf_kv_k[i] = nil;
                g_metal->buf_kv_v[i] = nil;
            }
            g_metal->buf_attn_q = nil;
            g_metal->buf_attn_scores = nil;
            g_metal->buf_attn_out = nil;
            g_metal->buf_attn_gate = nil;
            // CMD3 combine buffers
            g_metal->buf_moe_hidden = nil;
            g_metal->buf_combine_params = nil;
            g_metal->buf_cmd3_sum_sq = nil;
            // Shared event
            g_metal->pipeline_event = nil;
            // Delta-net GPU state buffers
            for (int i = 0; i < 48; i++) {
                g_metal->buf_delta_state[i] = nil;
                g_metal->buf_conv_state[i] = nil;
            }
            // Delta-net scratch buffers
            g_metal->buf_delta_q = nil;
            g_metal->buf_delta_k = nil;
            g_metal->buf_delta_v = nil;
            g_metal->buf_delta_g_decay = nil;
            g_metal->buf_delta_beta = nil;
            g_metal->buf_delta_output = nil;
            g_metal->buf_conv_input = nil;
            g_metal->buf_conv_output = nil;
            free(g_metal);
            g_metal = NULL;
        }

        ctx->loaded = 0;
        g_model_path_for_tokenizer = NULL;
        g_flashmoe_model_path[0] = '\0';
    }
}

void flashmoe_destroy(FlashMoEContext *ctx) {
    if (!ctx) return;
    flashmoe_unload(ctx);
    free(ctx);
}

// ============================================================================
// Generation — the core inference loop adapted for callback-based streaming
// ============================================================================

// All iOS generation paths must observe infer.m's fail-closed forward flag.
// fused_layer_forward() is void, so use the desktop checked wrapper instead of
// silently continuing after a layer reports a Metal/layout/cache failure.
static int flashmoe_forward_position_checked(FlashMoEContext *ctx, int pos) {
    return run_all_layers_checked(ctx->wf, ctx->hidden,
                                  ctx->kv_caches, ctx->layer_states,
                                  ctx->layer_mmaps, ctx->layer_fds,
                                  pos, ctx->K);
}

// A cancelled or failed turn must never leave partially advanced KV/GDN state
// eligible for continuation. We deliberately invalidate the conversation
// instead of carrying forward a half-committed turn. The next user turn can
// safely re-prefill the visible transcript from scratch.
static void flashmoe_abort_partial_generation(FlashMoEContext *ctx,
                                              const char *reason) {
    if (!ctx) return;
    if (reason) {
        snprintf(ctx->last_error, sizeof(ctx->last_error), "%s", reason);
    }
    flashmoe_reset(ctx);
}

// A sampled token is visible to the caller before it becomes an input to the
// next decode step. Before persisting conversation state, run that final emitted
// token through the transformer once so KV/delta state and current_pos describe
// exactly the transcript the user saw. Without this, continuation state trails
// the assistant output by one token. Returns the new position, or -1 on forward
// failure.
static int flashmoe_commit_emitted_token(FlashMoEContext *ctx, int token_id, int pos) {
    embed_lookup(ctx->wf, token_id, ctx->hidden);
    if (!flashmoe_forward_position_checked(ctx, pos)) {
        snprintf(ctx->last_error, sizeof(ctx->last_error),
                 "Forward failure while committing final emitted token at position %d", pos);
        return -1;
    }
    complete_deferred_experts();
    return pos + 1;
}

int flashmoe_generate(
    FlashMoEContext *ctx,
    const char *prompt,
    int max_tokens,
    FlashMoETokenCallback callback,
    void *user_data
) {
    if (!ctx || !ctx->loaded || !prompt) {
        if (ctx) snprintf(ctx->last_error, sizeof(ctx->last_error), "Engine not loaded or invalid arguments");
        return -1;
    }

    @autoreleasepool {
        atomic_store(&ctx->cancelled, 0);
        ctx->tokens_generated = 0;
        ctx->tokens_per_second = 0;

        double t0 = now_ms();

        // ---- Tokenize prompt ----
        PromptTokens *pt = encode_prompt_text_to_tokens(prompt);
        if (!pt) {
            snprintf(ctx->last_error, sizeof(ctx->last_error), "Failed to tokenize prompt");
            return -1;
        }
        if (!context_preflight("iOS generation", 0, pt->count, max_tokens)) {
            snprintf(ctx->last_error, sizeof(ctx->last_error),
                     "Context window full: prompt=%d generation=%d capacity=%d",
                     pt->count, max_tokens, g_kv_seq_len);
            free(pt->ids); free(pt);
            return -2;
        }

        int K = ctx->K;

        // ---- Reset state for new generation ----
        reset_delta_net_state();
        // Reset KV cache lengths
        for (int i = 0; i < g_cfg.num_layers; i++) {
            if (ctx->kv_caches[i]) {
                ctx->kv_caches[i]->len = 0;
            }
        }

        int pos = 0;

        // ---- Batch prefill: embed all prompt tokens ----
        float *embed_batch = NULL;
        if (pt->count > 1) {
            embed_batch = malloc((size_t)pt->count * HIDDEN_DIM * sizeof(float));
            for (int i = 0; i < pt->count; i++) {
                embed_lookup(ctx->wf, pt->ids[i], embed_batch + (size_t)i * HIDDEN_DIM);
            }
        }

        // ---- Prefill intermediate tokens (discard expert output) ----
        if (pt->count > 1) {
            double prefill_start = now_ms();
            for (int token_idx = 0; token_idx < pt->count - 1; token_idx++) {
                if (atomic_load(&ctx->cancelled)) {
                    free(embed_batch);
                    free(pt->ids); free(pt);
                    flashmoe_abort_partial_generation(ctx, "Generation cancelled");
                    return 0;
                }

                memcpy(ctx->hidden, embed_batch + (size_t)token_idx * HIDDEN_DIM,
                       HIDDEN_DIM * sizeof(float));

                if (!flashmoe_forward_position_checked(ctx, pos)) {
                    free(embed_batch);
                    free(pt->ids); free(pt);
                    flashmoe_abort_partial_generation(ctx, "Forward failure during prefill");
                    return -1;
                }
                discard_deferred_experts();
                pos++;

                // Report prefill progress via callback
                double prefill_elapsed = now_ms() - prefill_start;
                double prefill_tps = prefill_elapsed > 0 ? (token_idx + 1) * 1000.0 / prefill_elapsed : 0;
                ctx->tokens_per_second = prefill_tps;
                ctx->tokens_generated = -(token_idx + 1);  // negative = prefill in progress
                if (callback) {
                    char prefill_status[64];
                    snprintf(prefill_status, sizeof(prefill_status),
                             "[prefill %d/%d]", token_idx + 1, pt->count - 1);
                    callback(prefill_status, -1, -(token_idx + 1), prefill_tps, user_data);
                }
            }
            double prefill_total = now_ms() - prefill_start;
            NSLog(@"[prefill] %d tokens in %.0f ms (%.1f tok/s)",
                  pt->count - 1, prefill_total,
                  prefill_total > 0 ? (pt->count - 1) * 1000.0 / prefill_total : 0);
        }

        // ---- Last prefill token (need full hidden state) ----
        {
            if (embed_batch) {
                memcpy(ctx->hidden, embed_batch + (size_t)(pt->count - 1) * HIDDEN_DIM,
                       HIDDEN_DIM * sizeof(float));
            } else {
                embed_lookup(ctx->wf, pt->ids[0], ctx->hidden);
            }

            if (!flashmoe_forward_position_checked(ctx, pos)) {
                if (embed_batch) free(embed_batch);
                free(pt->ids); free(pt);
                flashmoe_abort_partial_generation(ctx, "Forward failure during generation");
                return -1;
            }
            complete_deferred_experts();
            pos++;
        }

        if (embed_batch) { free(embed_batch); embed_batch = NULL; }

        // ---- Final norm + LM head + sample first token ----
        if (ctx->final_norm_w) {
            float *normed = malloc(HIDDEN_DIM * sizeof(float));
            cpu_rms_norm(ctx->hidden, ctx->final_norm_w, normed, HIDDEN_DIM, RMS_NORM_EPS);
            memcpy(ctx->hidden, normed, HIDDEN_DIM * sizeof(float));
            free(normed);
        }

        lm_head_forward(ctx->wf, ctx->hidden, ctx->logits);
        int next_token = cpu_argmax(ctx->logits, VOCAB_SIZE);

        ctx->ttft_ms = now_ms() - t0;
        ctx->tokens_generated = 1;

        // ---- Invoke callback for first token ----
        const char *token_text = decode_token(ctx->vocab, next_token);
        NSLog(@"[gen] token %d: id=%d text=\"%s\"", ctx->tokens_generated, next_token,
              token_text ? token_text : "(null)");
        if (callback) {
            double gen_time = now_ms() - t0 - ctx->ttft_ms;
            double tps = gen_time > 0 ? 1000.0 / gen_time : 0;
            int stop = callback(token_text, next_token, ctx->tokens_generated, tps, user_data);
            if (stop) {
                int committed_pos = flashmoe_commit_emitted_token(ctx, next_token, pos);
                if (committed_pos < 0) {
                    free(pt->ids); free(pt);
                    flashmoe_abort_partial_generation(ctx, "Forward failure while committing stopped turn");
                    return -1;
                }
                pos = committed_pos;
                ctx->current_pos = pos;
                ctx->turn_count++;
                free(pt->ids); free(pt);
                ctx->total_time_ms = now_ms() - t0;
                return ctx->tokens_generated;
            }
        }

        int in_think = (next_token == THINK_START_TOKEN) ? 1 : 0;
        int think_tokens = 0;

        // ---- Auto-regressive generation loop ----
        double gen_start = now_ms();

        for (int gen = 1; gen < max_tokens; gen++) {
            // Check cancellation
            if (atomic_load(&ctx->cancelled)) break;

            // Check EOS
            if (next_token == EOS_TOKEN_1 || next_token == EOS_TOKEN_2) {
                NSLog(@"[gen] EOS token %d at position %d — stopping", next_token, ctx->tokens_generated);
                break;
            }

            // Think budget enforcement
            if (next_token == THINK_START_TOKEN) in_think = 1;
            if (next_token == THINK_END_TOKEN) in_think = 0;
            if (in_think) think_tokens++;

            // Embed + forward pass
            embed_lookup(ctx->wf, next_token, ctx->hidden);

            if (!flashmoe_forward_position_checked(ctx, pos)) {
                if (embed_batch) free(embed_batch);
                free(pt->ids); free(pt);
                flashmoe_abort_partial_generation(ctx, "Forward failure during generation");
                return -1;
            }
            complete_deferred_experts();
            pos++;

            // Final norm + LM head
            if (ctx->final_norm_w) {
                float *normed = malloc(HIDDEN_DIM * sizeof(float));
                cpu_rms_norm(ctx->hidden, ctx->final_norm_w, normed, HIDDEN_DIM, RMS_NORM_EPS);
                memcpy(ctx->hidden, normed, HIDDEN_DIM * sizeof(float));
                free(normed);
            }

            lm_head_forward(ctx->wf, ctx->hidden, ctx->logits);
            next_token = cpu_argmax(ctx->logits, VOCAB_SIZE);

            // Think budget: force end thinking
            if (in_think && g_think_budget > 0 && think_tokens >= g_think_budget) {
                next_token = THINK_END_TOKEN;
                in_think = 0;
            }

            ctx->tokens_generated++;

            // Compute tok/s
            double elapsed_gen = now_ms() - gen_start;
            ctx->tokens_per_second = elapsed_gen > 0 ? (ctx->tokens_generated - 1) * 1000.0 / elapsed_gen : 0;

            // Invoke callback
            token_text = decode_token(ctx->vocab, next_token);
            NSLog(@"[gen] token %d: id=%d text=\"%s\" (%.1f tok/s)",
                  ctx->tokens_generated, next_token,
                  token_text ? token_text : "(null)",
                  ctx->tokens_per_second);
            if (callback) {
                int stop = callback(token_text, next_token, ctx->tokens_generated,
                                    ctx->tokens_per_second, user_data);
                if (stop) break;
            }
        }

        ctx->total_time_ms = now_ms() - t0;
        double gen_elapsed = now_ms() - gen_start;
        if (ctx->tokens_generated > 1 && gen_elapsed > 0) {
            ctx->tokens_per_second = (ctx->tokens_generated - 1) * 1000.0 / gen_elapsed;
        }

        if (atomic_load(&ctx->cancelled)) {
            int emitted = ctx->tokens_generated;
            free(pt->ids); free(pt);
            flashmoe_abort_partial_generation(ctx, "Generation cancelled");
            return emitted;
        }

        // Persist state for KV cache reuse in next turn. The final emitted
        // token has not yet been used as model input, so commit it first.
        int committed_pos = flashmoe_commit_emitted_token(ctx, next_token, pos);
        if (committed_pos < 0) {
            free(pt->ids); free(pt);
            flashmoe_abort_partial_generation(ctx, "Forward failure while committing turn");
            return -1;
        }
        pos = committed_pos;
        ctx->current_pos = pos;
        ctx->turn_count++;

        free(pt->ids);
        free(pt);

        return ctx->tokens_generated;
    }
}

// ============================================================================
// Continuation generation — reuses KV cache from previous turns
// ============================================================================

int flashmoe_generate_continuation(
    FlashMoEContext *ctx,
    const char *user_content,
    int max_tokens,
    FlashMoETokenCallback callback,
    void *user_data
) {
    if (!ctx || !ctx->loaded || !user_content) {
        if (ctx) snprintf(ctx->last_error, sizeof(ctx->last_error), "Engine not loaded or invalid arguments");
        return -1;
    }
    if (ctx->turn_count == 0) {
        snprintf(ctx->last_error, sizeof(ctx->last_error), "No previous turn — use flashmoe_generate first");
        return -1;
    }

    @autoreleasepool {
        atomic_store(&ctx->cancelled, 0);
        ctx->tokens_generated = 0;
        ctx->tokens_per_second = 0;

        double t0 = now_ms();

        // Tokenize only the new turn (with continuation markers)
        PromptTokens *pt = flashmoe_tokenize_continuation_turn(user_content);
        if (!pt) {
            snprintf(ctx->last_error, sizeof(ctx->last_error), "Failed to tokenize continuation turn");
            return -1;
        }

        int K = ctx->K;
        int pos = ctx->current_pos;  // Resume from where we left off

        // Check the actual runtime CPU KV capacity before mutating state.
        // On iPhone this is commonly far below MAX_SEQ_LEN.
        if (!context_preflight("iOS continuation", pos, pt->count, max_tokens)) {
            NSLog(@"[FlashMoE] Context full (%d + %d + %d > %d)",
                  pos, pt->count, max_tokens, g_kv_seq_len);
            free(pt->ids); free(pt);
            snprintf(ctx->last_error, sizeof(ctx->last_error),
                     "Context window full, reset required");
            return -2;  // State is untouched; caller may re-prefill from scratch.
        }

        // NOTE: No reset_delta_net_state() — reuse KV caches and linear attention state

        // ---- Prefill continuation tokens ----
        float *embed_batch = NULL;
        if (pt->count > 1) {
            embed_batch = malloc((size_t)pt->count * HIDDEN_DIM * sizeof(float));
            for (int i = 0; i < pt->count; i++) {
                embed_lookup(ctx->wf, pt->ids[i], embed_batch + (size_t)i * HIDDEN_DIM);
            }
        }

        if (pt->count > 1) {
            for (int token_idx = 0; token_idx < pt->count - 1; token_idx++) {
                if (atomic_load(&ctx->cancelled)) {
                    free(embed_batch);
                    free(pt->ids); free(pt);
                    flashmoe_abort_partial_generation(ctx, "Generation cancelled");
                    return 0;
                }

                memcpy(ctx->hidden, embed_batch + (size_t)token_idx * HIDDEN_DIM,
                       HIDDEN_DIM * sizeof(float));

                if (!flashmoe_forward_position_checked(ctx, pos)) {
                    free(embed_batch);
                    free(pt->ids); free(pt);
                    flashmoe_abort_partial_generation(ctx, "Forward failure during prefill");
                    return -1;
                }
                discard_deferred_experts();
                pos++;
            }
        }

        // Last prefill token
        {
            if (embed_batch) {
                memcpy(ctx->hidden, embed_batch + (size_t)(pt->count - 1) * HIDDEN_DIM,
                       HIDDEN_DIM * sizeof(float));
            } else {
                embed_lookup(ctx->wf, pt->ids[0], ctx->hidden);
            }

            if (!flashmoe_forward_position_checked(ctx, pos)) {
                if (embed_batch) free(embed_batch);
                free(pt->ids); free(pt);
                flashmoe_abort_partial_generation(ctx, "Forward failure during generation");
                return -1;
            }
            complete_deferred_experts();
            pos++;
        }

        if (embed_batch) { free(embed_batch); embed_batch = NULL; }

        // ---- Final norm + LM head + sample first token ----
        if (ctx->final_norm_w) {
            float *normed = malloc(HIDDEN_DIM * sizeof(float));
            cpu_rms_norm(ctx->hidden, ctx->final_norm_w, normed, HIDDEN_DIM, RMS_NORM_EPS);
            memcpy(ctx->hidden, normed, HIDDEN_DIM * sizeof(float));
            free(normed);
        }

        lm_head_forward(ctx->wf, ctx->hidden, ctx->logits);
        int next_token = cpu_argmax(ctx->logits, VOCAB_SIZE);

        ctx->ttft_ms = now_ms() - t0;
        ctx->tokens_generated = 1;

        const char *token_text = decode_token(ctx->vocab, next_token);
        if (callback) {
            double gen_time = now_ms() - t0 - ctx->ttft_ms;
            double tps = gen_time > 0 ? 1000.0 / gen_time : 0;
            int stop = callback(token_text, next_token, ctx->tokens_generated, tps, user_data);
            if (stop) {
                int committed_pos = flashmoe_commit_emitted_token(ctx, next_token, pos);
                if (committed_pos < 0) {
                    free(pt->ids); free(pt);
                    flashmoe_abort_partial_generation(ctx, "Forward failure while committing stopped continuation");
                    return -1;
                }
                pos = committed_pos;
                free(pt->ids); free(pt);
                ctx->current_pos = pos;
                ctx->turn_count++;
                ctx->total_time_ms = now_ms() - t0;
                return ctx->tokens_generated;
            }
        }

        int in_think = (next_token == THINK_START_TOKEN) ? 1 : 0;
        int think_tokens = 0;

        // ---- Auto-regressive generation loop ----
        double gen_start = now_ms();

        for (int gen = 1; gen < max_tokens; gen++) {
            if (atomic_load(&ctx->cancelled)) break;

            if (next_token == EOS_TOKEN_1 || next_token == EOS_TOKEN_2) break;

            if (next_token == THINK_START_TOKEN) in_think = 1;
            if (next_token == THINK_END_TOKEN) in_think = 0;
            if (in_think) think_tokens++;

            embed_lookup(ctx->wf, next_token, ctx->hidden);

            if (!flashmoe_forward_position_checked(ctx, pos)) {
                if (embed_batch) free(embed_batch);
                free(pt->ids); free(pt);
                flashmoe_abort_partial_generation(ctx, "Forward failure during generation");
                return -1;
            }
            complete_deferred_experts();
            pos++;

            if (ctx->final_norm_w) {
                float *normed = malloc(HIDDEN_DIM * sizeof(float));
                cpu_rms_norm(ctx->hidden, ctx->final_norm_w, normed, HIDDEN_DIM, RMS_NORM_EPS);
                memcpy(ctx->hidden, normed, HIDDEN_DIM * sizeof(float));
                free(normed);
            }

            lm_head_forward(ctx->wf, ctx->hidden, ctx->logits);
            next_token = cpu_argmax(ctx->logits, VOCAB_SIZE);

            if (in_think && g_think_budget > 0 && think_tokens >= g_think_budget) {
                next_token = THINK_END_TOKEN;
                in_think = 0;
            }

            ctx->tokens_generated++;
            double elapsed_gen = now_ms() - gen_start;
            ctx->tokens_per_second = elapsed_gen > 0 ? (ctx->tokens_generated - 1) * 1000.0 / elapsed_gen : 0;

            token_text = decode_token(ctx->vocab, next_token);
            if (callback) {
                int stop = callback(token_text, next_token, ctx->tokens_generated,
                                    ctx->tokens_per_second, user_data);
                if (stop) break;
            }
        }

        ctx->total_time_ms = now_ms() - t0;
        double gen_elapsed = now_ms() - gen_start;
        if (ctx->tokens_generated > 1 && gen_elapsed > 0) {
            ctx->tokens_per_second = (ctx->tokens_generated - 1) * 1000.0 / gen_elapsed;
        }

        if (atomic_load(&ctx->cancelled)) {
            int emitted = ctx->tokens_generated;
            free(pt->ids); free(pt);
            flashmoe_abort_partial_generation(ctx, "Generation cancelled");
            return emitted;
        }

        int committed_pos = flashmoe_commit_emitted_token(ctx, next_token, pos);
        if (committed_pos < 0) {
            free(pt->ids); free(pt);
            flashmoe_abort_partial_generation(ctx, "Forward failure while committing continuation");
            return -1;
        }
        pos = committed_pos;
        ctx->current_pos = pos;
        ctx->turn_count++;

        free(pt->ids);
        free(pt);

        return ctx->tokens_generated;
    }
}

void flashmoe_cancel(FlashMoEContext *ctx) {
    if (!ctx) return;
    atomic_store(&ctx->cancelled, 1);
}

void flashmoe_reset(FlashMoEContext *ctx) {
    if (!ctx || !ctx->loaded) return;

    @autoreleasepool {
        // Wait for any in-flight GPU work
        if (g_deferred.active) {
            [g_deferred.cmd_experts waitUntilCompleted];
            g_deferred.active = 0;
            g_deferred.cmd_experts = nil;
        }

        // Reset delta-net state
        reset_delta_net_state();

        // Reset KV caches
        for (int i = 0; i < g_cfg.num_layers; i++) {
            if (ctx->kv_caches[i]) {
                ctx->kv_caches[i]->len = 0;
            }
        }

        // Reset conversation position
        ctx->current_pos = 0;
        ctx->turn_count = 0;

        // Reset stats
        ctx->tokens_generated = 0;
        ctx->tokens_per_second = 0;
        ctx->total_time_ms = 0;
        ctx->ttft_ms = 0;
    }
}

void flashmoe_get_stats(FlashMoEContext *ctx, FlashMoEStats *stats) {
    if (!ctx || !stats) return;

    memset(stats, 0, sizeof(FlashMoEStats));

    if (ctx->loaded) {
        snprintf(stats->model_name, sizeof(stats->model_name), "%s",
                 g_model_path_for_tokenizer ? g_model_path_for_tokenizer : "unknown");
        stats->num_layers = g_cfg.num_layers;
        stats->num_linear_layers = g_cfg.num_linear_layers;
        stats->num_full_attn_layers = g_cfg.num_full_attn_layers;
        stats->num_experts = g_cfg.num_experts;
        stats->active_experts_k = ctx->K;
        stats->hidden_dim = HIDDEN_DIM;
        stats->vocab_size = VOCAB_SIZE;
        stats->num_attn_heads = g_cfg.num_attn_heads;
        stats->num_kv_heads = g_cfg.num_kv_heads;
        stats->head_dim = g_cfg.head_dim;
        stats->moe_intermediate = g_cfg.moe_intermediate;
        stats->is_smoke_test = (g_cfg.num_experts < 512) ? 1 : 0;

        // Determine expert quantization bits
        if (g_use_2bit)          stats->expert_quant_bits = 2;
        else if (g_use_q3_experts) stats->expert_quant_bits = 3;
        else                      stats->expert_quant_bits = 4;

        // Dense weights are MLX 4-bit (group_size=64) with BF16 scales+biases
        // Effective bits/param: 4 (weight) + 16/64 (scale) + 16/64 (bias) = 4.5 bits/param
        stats->dense_quant_bits = 4;
        stats->dense_avg_bits = 4.5f;

        stats->weight_file_bytes = ctx->wf ? ctx->wf->size : 0;
        stats->expert_size_each = (size_t)active_expert_size();

        // Compute total expert file bytes
        size_t total_expert = 0;
        for (int i = 0; i < g_cfg.num_layers; i++) {
            total_expert += ctx->layer_mmap_sizes[i];
        }
        stats->expert_file_bytes = total_expert;

        // Approximate Metal buffer bytes
        stats->metal_buffer_bytes = (size_t)g_cfg.expert_size_computed * MAX_K * 2 +  // expert data (double-buffered)
                                    (size_t)HIDDEN_DIM * sizeof(float) * 20 +  // various working buffers
                                    (size_t)VOCAB_SIZE * sizeof(float);          // logits
    }

    stats->tokens_per_second = ctx->tokens_per_second;
    stats->tokens_generated = ctx->tokens_generated;
    stats->total_time_ms = ctx->total_time_ms;
    stats->ttft_ms = ctx->ttft_ms;
}

int flashmoe_validate_model(const char *model_path) {
    if (!model_path) return -1;

    // Check config.json
    char path[1024];
    snprintf(path, sizeof(path), "%s/config.json", model_path);
    if (access(path, R_OK) != 0) return -1;

    // Check model_weights.bin
    snprintf(path, sizeof(path), "%s/model_weights.bin", model_path);
    if (access(path, R_OK) != 0) return -1;

    // Check model_weights.json
    snprintf(path, sizeof(path), "%s/model_weights.json", model_path);
    if (access(path, R_OK) != 0) return -1;

    // This iOS target is architecture-locked to the 40-layer 35B model.
    // A package is not valid merely because layer_00 exists: require every
    // expert layer for at least one supported quantization layout.
    const char *dirs[] = {
        "packed_experts", "packed_experts_tiered", "packed_experts_2bit"
    };
    int complete_package = 0;
    for (int d = 0; d < 3 && !complete_package; d++) {
        int complete = 1;
        if (d == 1) {
            snprintf(path, sizeof(path), "%s/%s/tiered_manifest.json",
                     model_path, dirs[d]);
            if (!flashmoe_readable_nonempty_file(path)) complete = 0;
        }
        for (int layer = 0; layer < 40 && complete; layer++) {
            snprintf(path, sizeof(path), "%s/%s/layer_%02d.bin",
                     model_path, dirs[d], layer);
            if (!flashmoe_readable_nonempty_file(path)) complete = 0;
        }
        if (complete) complete_package = 1;
    }
    if (!complete_package) return -1;

    snprintf(path, sizeof(path), "%s/vocab.bin", model_path);
    if (!flashmoe_readable_nonempty_file(path)) return -1;
    snprintf(path, sizeof(path), "%s/tokenizer.bin", model_path);
    if (!flashmoe_readable_nonempty_file(path)) return -1;

    return 0;
}

int flashmoe_turn_count(FlashMoEContext *ctx) {
    if (!ctx) return 0;
    return ctx->turn_count;
}

const char *flashmoe_last_error(FlashMoEContext *ctx) {
    if (!ctx) return "NULL context";
    return ctx->last_error;
}
