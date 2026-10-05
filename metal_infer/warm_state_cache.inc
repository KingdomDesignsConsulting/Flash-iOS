// Raw, process-independent persistence for a single fully-prefilled prefix.
// Included after ServeStateSnapshot capture/restore so the same state layout
// is used for runtime and disk caches.
#define WARM_STATE_VERSION 1U
#define WARM_STATE_ZSTD_VERSION 2U // Storage only; not part of execution compatibility.
#define WARM_STATE_LAYOUT_VERSION 1U
/*
 * CACHE CORRECTNESS CONTRACT:
 * Any inference-math change capable of changing serialized prefix state MUST
 * either alter a value in warm_execution_mode_hash() or increment
 * WARM_STATE_EXECUTION_VERSION.
 * Do not bump for HTTP, tool, logging, or UI-only changes.
 */
#define WARM_STATE_EXECUTION_VERSION 1U
#define WARM_STATE_MAX_BYTES (UINT64_C(1) << 31)

typedef struct {
    char magic[8];
    uint32_t version, header_bytes, layout_version;
    uint64_t compatibility, source_hash, profile_hash; // source_hash = exact prefix-token signature
    uint64_t payload_bytes, payload_hash;
    uint64_t tool_sig, token_sig;
    uint32_t token_count, pos;
    uint32_t layers, kv_dim, conv_bytes, ssm_bytes, gpu_layers;
    int32_t kv_len[MAX_LAYERS];
} WarmStateHeader;

typedef struct {
    uint64_t stored_bytes, stored_hash;
} WarmStateZstdStorage;

static NSString *warm_state_zstd_path(NSString *path) {
    NSString *name = path.lastPathComponent;
    if (![name hasSuffix:@".state"] || name.length < 24) return nil;
    return [[path stringByDeletingLastPathComponent] stringByAppendingPathComponent:
        [@"zstd-" stringByAppendingString:name]];
}

static NSString *warm_state_identity_path(NSString *legacy_path) {
    NSString *name = legacy_path.lastPathComponent;
    if (![name hasSuffix:@".state"] || name.length < 24) return nil;
    return [[legacy_path stringByDeletingLastPathComponent]
        stringByAppendingPathComponent:[@"id2-" stringByAppendingString:name]];
}

static uint64_t warm_hash_bytes(uint64_t h, const void *data, size_t size) {
    const uint8_t *p = data;
    for (size_t i = 0; i < size; i++) {
        h ^= p[i];
        h *= UINT64_C(1099511628211);
    }
    return h;
}

static uint64_t warm_hash_string(uint64_t h, const char *s) {
    return warm_hash_bytes(h, s, strlen(s) + 1);
}

static int warm_hash_file(const char *path, uint64_t *result) {
    int fd = open(path, O_RDONLY);
    if (fd < 0) return 0;
    uint64_t h = UINT64_C(14695981039346656037);
    uint8_t buf[16384];
    ssize_t n;
    while ((n = read(fd, buf, sizeof(buf))) > 0)
        h = warm_hash_bytes(h, buf, (size_t)n);
    int ok = n == 0;
    if (close(fd) != 0) ok = 0;
    if (ok) *result = h;
    return ok;
}

static int warm_hash_stat_identity(uint64_t *h, const char *path,
                                   int legacy_device, uint64_t device_override) {
    struct stat st;
    if (!path || stat(path, &st) != 0) return 0;
    *h = warm_hash_string(*h, path);
    if (legacy_device) {
        uint64_t values[] = {device_override ? device_override : (uint64_t)st.st_dev,
            (uint64_t)st.st_ino, (uint64_t)st.st_size,
            (uint64_t)st.st_mtimespec.tv_sec, (uint64_t)st.st_mtimespec.tv_nsec};
        *h = warm_hash_bytes(*h, values, sizeof(values));
    } else {
        uint64_t values[] = {(uint64_t)st.st_ino, (uint64_t)st.st_size,
            (uint64_t)st.st_mtimespec.tv_sec, (uint64_t)st.st_mtimespec.tv_nsec};
        *h = warm_hash_bytes(*h, values, sizeof(values));
    }
    return 1;
}

static int warm_hash_small_file_identity(uint64_t *h, const char *content_path,
                                         const char *identity_path) {
    struct stat st;
    if (!content_path || !identity_path ||
        stat(content_path, &st) != 0 || !S_ISREG(st.st_mode) ||
        st.st_size < 0 || st.st_size > 64 * 1024 * 1024) return 0;
    uint64_t content = 0;
    if (!warm_hash_file(content_path, &content)) return 0;
    *h = warm_hash_string(*h, identity_path);
    *h = warm_hash_bytes(*h, &content, sizeof(content));
    return 1;
}

static int warm_hash_small_file(uint64_t *h, const char *path) {
    return warm_hash_small_file_identity(h, path, path);
}

static uint64_t warm_execution_mode_hash(int K) {
    uint64_t shape[] = {WARM_STATE_VERSION, WARM_STATE_LAYOUT_VERSION,
        WARM_STATE_EXECUTION_VERSION, (uint64_t)NUM_LAYERS,
        (uint64_t)NUM_KV_HEADS, (uint64_t)HEAD_DIM,
        (uint64_t)LINEAR_NUM_V_HEADS, (uint64_t)LINEAR_VALUE_DIM,
        (uint64_t)LINEAR_KEY_DIM, (uint64_t)LINEAR_CONV_DIM,
        (uint64_t)CONV_KERNEL_SIZE, (uint64_t)g_kv_seq_len,
        (uint64_t)g_use_tiered, (uint64_t)g_use_2bit,
        (uint64_t)g_use_q3_experts, (uint64_t)g_use_lz4,
        (uint64_t)K,
        (uint64_t)(g_metal && g_metal->delta_net_step),
        (uint64_t)g_gpu_resident_moe_enabled,
        (uint64_t)g_oproj_v3_enabled,
        (uint64_t)g_tiny_matvec_fast_enabled,
        (uint64_t)g_cmd12_chain_enabled,
        (uint64_t)g_cmd12_full_chain_enabled,
        (uint64_t)gpu_linear_attn_enabled,
        (uint64_t)linear_attn_bypass};
    uint64_t h = warm_hash_bytes(UINT64_C(14695981039346656037),
                                 shape, sizeof(shape));
    // v2 CPU recurrence semantics: pre-fix --cpu-linear checkpoints stored
    // stale CPU SSM state because the old fallback advanced GPU recurrence.
    // Hash the marker only in CPU-linear mode so ordinary GPU and bypass
    // checkpoints retain their exact pre-existing compatibility identity.
    if (!gpu_linear_attn_enabled && !linear_attn_bypass)
        h = warm_hash_string(h, "cpu-linear-recurrence-v2");
    return h;
}

static int warm_state_compatibility_identity_ex(const char *weights,
                                                const char *manifest,
                                                const char *vocab, WeightFile *wf,
                                                int *layer_fds, int K,
                                                int legacy_device,
                                                uint64_t device_override,
                                                const char *shader_identity_override,
                                                int include_gguf_json,
                                                uint64_t *result) {
    uint64_t h = UINT64_C(14695981039346656037);
    if (!legacy_device)
        h = warm_hash_string(h, "warm-compatibility-identity-v2-no-device");
    // Optional conservative policy for later, when binary-level invalidation
    // is preferable to preserving checkpoints across unrelated rebuilds:
    // NSString *executable = [[[NSBundle mainBundle] executablePath]
    //     stringByResolvingSymlinksInPath];
    // if (executable.length == 0 ||
    //     !warm_hash_file(executable.fileSystemRepresentation, &h)) return 0;
    if (!warm_hash_stat_identity(&h, weights, legacy_device, device_override) ||
        !warm_hash_small_file(&h, manifest) ||
        !warm_hash_small_file(&h, vocab)) return 0;
    NSString *shader_path = [infer_executable_directory()
        stringByAppendingPathComponent:@"shaders.metal"];
    if (!shader_path) return 0;
    const char *shader_content_path = shader_path.fileSystemRepresentation;
    const char *shader_identity_path = shader_identity_override
        ? shader_identity_override : shader_content_path;
    if (!warm_hash_small_file_identity(&h, shader_content_path,
                                       shader_identity_path)) return 0;
    if (g_model_path_for_tokenizer) {
        char path[PATH_MAX];
        for (const char *name[] = {"config.json", "tokenizer.bin",
                 "packed_experts_tiered/tiered_manifest.json", NULL},
                 **p = name; *p; p++) {
            if (snprintf(path, sizeof(path), "%s/%s", g_model_path_for_tokenizer, *p)
                    >= (int)sizeof(path)) return 0;
            if (access(path, F_OK) == 0 && !warm_hash_small_file(&h, path)) return 0;
        }
    }
    const char *gguf_paths[] = {wf->gguf_embedding_path, wf->gguf_full_attn_path,
        wf->gguf_qkv_path, wf->gguf_linear_path, wf->gguf_shared_path,
        wf->gguf_lm_head_path};
    for (size_t i = 0; i < sizeof(gguf_paths)/sizeof(gguf_paths[0]); i++) {
        if (gguf_paths[i] && !warm_hash_stat_identity(&h, gguf_paths[i],
                legacy_device, device_override)) return 0;
    }
    // The binary identity alone is insufficient for custom overlays: these
    // manifests choose layer/role/offset mappings within the same binary.
    if (include_gguf_json) {
        const char *gguf_json_paths[] = {wf->gguf_full_attn_json_path,
            wf->gguf_qkv_json_path, wf->gguf_linear_json_path,
            wf->gguf_shared_json_path};
        for (size_t i = 0; i < sizeof(gguf_json_paths)/sizeof(gguf_json_paths[0]); i++) {
            if (gguf_json_paths[i] && !warm_hash_small_file(&h, gguf_json_paths[i]))
                return 0;
        }
    }
    uint64_t execution = warm_execution_mode_hash(K);
    h = warm_hash_bytes(h, &execution, sizeof(execution));
    for (int i = 0; i < NUM_LAYERS; i++) {
        struct stat st;
        if (layer_fds[i] < 0 || fstat(layer_fds[i], &st) != 0) return 0;
        if (legacy_device) {
            uint64_t values[] = {device_override ? device_override : (uint64_t)st.st_dev,
                (uint64_t)st.st_ino, (uint64_t)st.st_size,
                (uint64_t)st.st_mtimespec.tv_sec, (uint64_t)st.st_mtimespec.tv_nsec};
            h = warm_hash_bytes(h, values, sizeof(values));
        } else {
            uint64_t values[] = {(uint64_t)st.st_ino, (uint64_t)st.st_size,
                (uint64_t)st.st_mtimespec.tv_sec, (uint64_t)st.st_mtimespec.tv_nsec};
            h = warm_hash_bytes(h, values, sizeof(values));
        }
        if (g_layer_fds_cold && g_layer_fds_cold[i] >= 0) {
            if (fstat(g_layer_fds_cold[i], &st) != 0) return 0;
            if (legacy_device) {
                uint64_t values[] = {device_override ? device_override : (uint64_t)st.st_dev,
                    (uint64_t)st.st_ino, (uint64_t)st.st_size,
                    (uint64_t)st.st_mtimespec.tv_sec, (uint64_t)st.st_mtimespec.tv_nsec};
                h = warm_hash_bytes(h, values, sizeof(values));
            } else {
                uint64_t values[] = {(uint64_t)st.st_ino, (uint64_t)st.st_size,
                    (uint64_t)st.st_mtimespec.tv_sec, (uint64_t)st.st_mtimespec.tv_nsec};
                h = warm_hash_bytes(h, values, sizeof(values));
            }
        }
    }
    *result = h;
    return 1;
}

static int warm_state_compatibility_identity(const char *weights,
                                             const char *manifest,
                                             const char *vocab, WeightFile *wf,
                                             int *layer_fds, int K,
                                             int legacy_device,
                                             uint64_t device_override,
                                             uint64_t *result) {
    return warm_state_compatibility_identity_ex(weights, manifest, vocab, wf,
                                                layer_fds, K, legacy_device,
                                                device_override, NULL, 1, result);
}

static int warm_state_compatibility(const char *weights, const char *manifest,
                                    const char *vocab, WeightFile *wf,
                                    int *layer_fds, int K,
                                    uint64_t *result) {
    return warm_state_compatibility_identity(weights, manifest, vocab, wf,
                                             layer_fds, K, 0, 0, result);
}

static int warm_write_all(int fd, const void *data, size_t size, uint64_t *hash) {
    const uint8_t *p = data;
    size_t remaining = size;
    while (remaining) {
        ssize_t n = write(fd, p, remaining);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return 0;
        p += n;
        remaining -= (size_t)n;
    }
    if (hash) *hash = warm_hash_bytes(*hash, data, size);
    return 1;
}

static int warm_read_all(int fd, void *data, size_t size, uint64_t *hash) {
    uint8_t *p = data;
    size_t remaining = size;
    while (remaining) {
        ssize_t n = read(fd, p, remaining);
        if (n < 0 && errno == EINTR) continue;
        if (n <= 0) return 0;
        p += n;
        remaining -= (size_t)n;
    }
    if (hash) *hash = warm_hash_bytes(*hash, data, size);
    return 1;
}

static int warm_verify_payload(int fd, uint64_t bytes, uint64_t expected_hash) {
    uint8_t buffer[65536];
    uint64_t hash = UINT64_C(14695981039346656037);
    while (bytes) {
        size_t chunk = bytes < sizeof(buffer) ? (size_t)bytes : sizeof(buffer);
        if (!warm_read_all(fd, buffer, chunk, &hash)) return 0;
        bytes -= chunk;
    }
    return hash == expected_hash;
}

static int warm_add_bytes(uint64_t *total, uint64_t count, uint64_t unit) {
    if (unit && count > (WARM_STATE_MAX_BYTES - *total) / unit) return 0;
    *total += count * unit;
    return 1;
}

static int warm_payload_bytes(const WarmStateHeader *head,
                              KVCache **kv_caches, void **layer_states,
                              uint64_t *result) {
    uint64_t size = 0;
    for (int i = 0; i < NUM_LAYERS; i++) {
        if (kv_caches[i]) {
            if (head->kv_len[i] < 0 || head->kv_len[i] > (int)head->pos ||
                head->kv_len[i] > g_kv_seq_len) return 0;
            if (!warm_add_bytes(&size, (uint64_t)head->kv_len[i],
                                2ULL * head->kv_dim * sizeof(float))) return 0;
        } else if (head->kv_len[i] != 0) return 0;
        if (layer_states[i] &&
            !warm_add_bytes(&size, 1, (uint64_t)head->conv_bytes + head->ssm_bytes)) return 0;
    }
    if (!warm_add_bytes(&size, head->gpu_layers,
        64ULL * 128 * 128 * sizeof(float) + 3ULL * 12288 * sizeof(float))) return 0;
    *result = size;
    return 1;
}

static int warm_state_header_valid(const WarmStateHeader *head,
                                   uint64_t compatibility, uint64_t source_hash,
                                   uint64_t profile_hash,
                                   KVCache **kv_caches, void **layer_states) {
    if (memcmp(head->magic, "FWSTATE1", 8) ||
        (head->version != WARM_STATE_VERSION &&
         head->version != WARM_STATE_ZSTD_VERSION) ||
        head->layout_version != WARM_STATE_LAYOUT_VERSION ||
        head->header_bytes != sizeof(*head) +
            (head->version == WARM_STATE_ZSTD_VERSION ? sizeof(WarmStateZstdStorage) : 0) ||
        head->compatibility != compatibility ||
        head->source_hash != source_hash ||
        head->profile_hash != profile_hash ||
        head->layers != (uint32_t)NUM_LAYERS ||
        head->kv_dim != (uint32_t)(NUM_KV_HEADS * HEAD_DIM) ||
        head->conv_bytes != (uint32_t)((CONV_KERNEL_SIZE-1) * LINEAR_CONV_DIM * sizeof(float)) ||
        head->ssm_bytes != (uint32_t)(LINEAR_NUM_V_HEADS * LINEAR_VALUE_DIM * LINEAR_KEY_DIM * sizeof(float)) ||
        head->gpu_layers != (uint32_t)(snapshot_uses_gpu_linear_state()
            ? g_cfg.num_linear_layers : 0) ||
        head->gpu_layers > 48 ||
        head->token_count == 0 || head->token_count > TOOL_PREFIX_CACHE_MAX_TOKENS ||
        head->pos != head->token_count || head->tool_sig == 0 || head->token_sig == 0 ||
        head->payload_bytes == 0 || head->payload_bytes > WARM_STATE_MAX_BYTES)
        return 0;
    uint64_t expected_bytes = 0;
    return warm_payload_bytes(head, kv_caches, layer_states, &expected_bytes) &&
           expected_bytes == head->payload_bytes;
}

static int warm_transfer_buffer(int fd, void **buffer, size_t size,
                                int writing, uint64_t *hash) {
    if (!size) return 1;
    if (!writing) {
        *buffer = malloc(size);
        if (!*buffer) return 0;
    }
    if (!*buffer) return 0;
    return writing ? warm_write_all(fd, *buffer, size, hash)
                   : warm_read_all(fd, *buffer, size, hash);
}

static int warm_transfer_snapshot(int fd, ServeStateSnapshot *snap,
                                  const WarmStateHeader *head,
                                  KVCache **kv_caches, void **layer_states,
                                  int writing, uint64_t *hash) {
    for (int i = 0; i < NUM_LAYERS; i++) {
        if (kv_caches[i]) {
            size_t sz = (size_t)head->kv_len[i] * head->kv_dim * sizeof(float);
            if (!warm_transfer_buffer(fd, (void **)&snap->k_snapshot[i], sz, writing, hash) ||
                !warm_transfer_buffer(fd, (void **)&snap->v_snapshot[i], sz, writing, hash))
                return 0;
        }
        if (layer_states[i]) {
            if (!warm_transfer_buffer(fd, (void **)&snap->la_conv_snapshot[i],
                                      head->conv_bytes, writing, hash) ||
                !warm_transfer_buffer(fd, (void **)&snap->la_ssm_snapshot[i],
                                      head->ssm_bytes, writing, hash))
                return 0;
        }
    }
    for (int i = 0; i < (int)head->gpu_layers; i++) {
        if (!warm_transfer_buffer(fd, &snap->gpu_delta_snapshot[i],
                                  64 * 128 * 128 * sizeof(float), writing, hash) ||
            !warm_transfer_buffer(fd, &snap->gpu_conv_snapshot[i],
                                  3 * 12288 * sizeof(float), writing, hash))
            return 0;
    }
    return 1;
}

static int warm_memory_buffer(uint8_t **cursor, size_t *remaining,
                              void **buffer, size_t size, int writing) {
    if (size > *remaining) return 0;
    if (size) {
        if (!writing) {
            *buffer = malloc(size);
            if (!*buffer) return 0;
            memcpy(*buffer, *cursor, size);
        } else {
            if (!*buffer) return 0;
            memcpy(*cursor, *buffer, size);
        }
        *cursor += size;
        *remaining -= size;
    }
    return 1;
}

static int warm_transfer_snapshot_memory(uint8_t *payload, size_t size,
                                         ServeStateSnapshot *snap,
                                         const WarmStateHeader *head,
                                         KVCache **kv_caches, void **layer_states,
                                         int writing) {
    uint8_t *cursor = payload;
    size_t remaining = size;
    for (int i = 0; i < NUM_LAYERS; i++) {
        if (kv_caches[i]) {
            size_t bytes = (size_t)head->kv_len[i] * head->kv_dim * sizeof(float);
            if (!warm_memory_buffer(&cursor, &remaining,
                    (void **)&snap->k_snapshot[i], bytes, writing) ||
                !warm_memory_buffer(&cursor, &remaining,
                    (void **)&snap->v_snapshot[i], bytes, writing)) return 0;
        }
        if (layer_states[i] &&
            (!warm_memory_buffer(&cursor, &remaining,
                (void **)&snap->la_conv_snapshot[i], head->conv_bytes, writing) ||
             !warm_memory_buffer(&cursor, &remaining,
                (void **)&snap->la_ssm_snapshot[i], head->ssm_bytes, writing))) return 0;
    }
    for (int i = 0; i < (int)head->gpu_layers; i++) {
        if (!warm_memory_buffer(&cursor, &remaining,
                &snap->gpu_delta_snapshot[i], 64 * 128 * 128 * sizeof(float), writing) ||
            !warm_memory_buffer(&cursor, &remaining,
                &snap->gpu_conv_snapshot[i], 3 * 12288 * sizeof(float), writing)) return 0;
    }
    return remaining == 0;
}

static int warm_state_load(NSString *path, ToolPrefixCacheEntry *entry,
                           KVCache **kv_caches, void **layer_states,
                           uint64_t compatibility, uint64_t source_hash,
                           uint64_t profile_hash,
                           const ToolPrefixCacheEntry *expected_prefix) {
    int fd = open(path.fileSystemRepresentation, O_RDONLY | O_NOFOLLOW);
    if (fd < 0) {
        fprintf(stderr, "[warm-state] cache miss: %s\n", strerror(errno));
        return 0;
    }
    double start_ms = now_ms();
    WarmStateHeader head = {0};
    WarmStateZstdStorage storage = {0};
    struct stat st = {0};
    int valid = fstat(fd, &st) == 0 && S_ISREG(st.st_mode) &&
        warm_read_all(fd, &head, sizeof(head), NULL) &&
        warm_state_header_valid(&head, compatibility, source_hash,
                                profile_hash, kv_caches, layer_states) &&
        expected_prefix &&
        head.tool_sig == expected_prefix->tool_sig &&
        head.token_sig == expected_prefix->token_sig &&
        expected_prefix->token_count > 0 &&
        head.token_count == (uint32_t)expected_prefix->token_count;
    if (valid && head.version == WARM_STATE_ZSTD_VERSION) {
        // header_valid() has already bounded payload_bytes and checked its geometry.
        size_t max_stored = ZSTD_compressBound((size_t)head.payload_bytes);
        int storage_read = warm_read_all(fd, &storage, sizeof(storage), NULL);
        if (storage_read && storage.stored_bytes > max_stored)
            fprintf(stderr, "[warm-state] cache invalid: compressed section exceeds Zstd bound\n");
        valid = storage_read &&
            max_stored > 0 &&
            storage.stored_bytes > 0 &&
            storage.stored_bytes <= max_stored &&
            storage.stored_bytes <= WARM_STATE_MAX_BYTES &&
            storage.stored_bytes <= UINT64_MAX - head.header_bytes &&
            st.st_size == (off_t)(head.header_bytes + storage.stored_bytes);
    } else if (valid) {
        valid = st.st_size == (off_t)(sizeof(head) + head.payload_bytes);
    }
    if (!valid) {
        fprintf(stderr, "[warm-state] cache invalid: header, identity, layout or size mismatch\n");
        if (S_ISREG(st.st_mode)) {
            uint64_t expected_bytes = 0;
            int geometry_ok = warm_payload_bytes(&head, kv_caches, layer_states,
                                                  &expected_bytes);
            fprintf(stderr,
                "[warm-state] diagnostic: version=%u/%u header=%u/%zu layout=%u/%u compatibility=%016llx/%016llx source=%016llx/%016llx profile=%016llx/%016llx layers=%u/%u kv_dim=%u/%u conv=%u/%u ssm=%u/%u gpu_layers=%u/%u payload=%llu/%llu geometry=%s file=%lld/%llu tool=%016llx/%016llx token=%016llx/%016llx count=%u/%d\n",
                head.version, WARM_STATE_VERSION, head.header_bytes, sizeof(head),
                head.layout_version, WARM_STATE_LAYOUT_VERSION,
                (unsigned long long)head.compatibility,
                (unsigned long long)compatibility,
                (unsigned long long)head.source_hash,
                (unsigned long long)source_hash,
                (unsigned long long)head.profile_hash,
                (unsigned long long)profile_hash,
                head.layers, NUM_LAYERS, head.kv_dim, NUM_KV_HEADS * HEAD_DIM,
                head.conv_bytes, (CONV_KERNEL_SIZE-1) * LINEAR_CONV_DIM * (int)sizeof(float),
                head.ssm_bytes, LINEAR_NUM_V_HEADS * LINEAR_VALUE_DIM * LINEAR_KEY_DIM * (int)sizeof(float),
                head.gpu_layers, snapshot_uses_gpu_linear_state() ? g_cfg.num_linear_layers : 0,
                (unsigned long long)head.payload_bytes,
                (unsigned long long)expected_bytes, geometry_ok ? "yes" : "no",
                (long long)st.st_size,
                (unsigned long long)(head.header_bytes + head.payload_bytes),
                (unsigned long long)head.tool_sig,
                (unsigned long long)(expected_prefix ? expected_prefix->tool_sig : 0),
                (unsigned long long)head.token_sig,
                (unsigned long long)(expected_prefix ? expected_prefix->token_sig : 0),
                head.token_count, expected_prefix ? expected_prefix->token_count : 0);
        }
        close(fd);
        return 0;
    }
    ServeStateSnapshot *snap = &entry->snapshot;
    double read_ms = 0, decompress_ms = 0, validation_ms = 0, copy_ms = 0;
    if (head.version == WARM_STATE_ZSTD_VERSION) {
        double tick = now_ms();
        uint8_t *stored = malloc((size_t)storage.stored_bytes);
        valid = stored && warm_read_all(fd, stored, (size_t)storage.stored_bytes, NULL);
        read_ms = now_ms() - tick;
        tick = now_ms();
        valid = valid && warm_hash_bytes(UINT64_C(14695981039346656037),
            stored, (size_t)storage.stored_bytes) == storage.stored_hash;
        validation_ms = now_ms() - tick;
        uint8_t *payload = valid ? malloc((size_t)head.payload_bytes) : NULL;
        if (!payload) valid = 0;
        if (valid) {
            tick = now_ms();
            size_t decoded = ZSTD_decompress(payload, (size_t)head.payload_bytes,
                                              stored, (size_t)storage.stored_bytes);
            decompress_ms = now_ms() - tick;
            valid = !ZSTD_isError(decoded) && decoded == head.payload_bytes;
        }
        free(stored);
        if (valid) {
            tick = now_ms();
            valid = warm_hash_bytes(UINT64_C(14695981039346656037),
                payload, (size_t)head.payload_bytes) == head.payload_hash;
            validation_ms += now_ms() - tick;
        }
        if (valid) {
            tick = now_ms();
            serve_state_snapshot_free(snap);
            for (int i = 0; i < NUM_LAYERS; i++) snap->kv_len[i] = head.kv_len[i];
            valid = warm_transfer_snapshot_memory(payload, (size_t)head.payload_bytes,
                snap, &head, kv_caches, layer_states, 0);
            copy_ms = now_ms() - tick;
        }
        free(payload);
    } else {
        // Reject damaged payloads before allocating a checkpoint-sized snapshot.
        double tick = now_ms();
        valid = warm_verify_payload(fd, head.payload_bytes, head.payload_hash) &&
            lseek(fd, (off_t)sizeof(head), SEEK_SET) == (off_t)sizeof(head);
        validation_ms = now_ms() - tick;
        if (valid) {
            serve_state_snapshot_free(snap);
            for (int i = 0; i < NUM_LAYERS; i++) snap->kv_len[i] = head.kv_len[i];
            uint64_t hash = UINT64_C(14695981039346656037);
            tick = now_ms();
            valid = warm_transfer_snapshot(fd, snap, &head, kv_caches, layer_states,
                                           0, &hash) && hash == head.payload_hash;
            copy_ms = now_ms() - tick;
        }
    }
    close(fd);
    if (!valid) {
        fprintf(stderr, "[warm-state] cache invalid: truncated payload or checksum mismatch\n");
        serve_state_snapshot_free(snap);
        return 0;
    }
    snap->pos = (int)head.pos;
    snap->valid = 1;
    entry->tool_sig = head.tool_sig;
    entry->token_sig = head.token_sig;
    entry->token_count = (int)head.token_count;
    entry->pinned = 1;
    fprintf(stderr,
        "[warm-state] valid snapshot: format=%s tokens=%u bytes=%llu; loaded in %.0fms; read=%.0fms decompress=%.0fms validate=%.0fms copy=%.0fms; pinned slot=0\n",
        head.version == WARM_STATE_ZSTD_VERSION ? "zstd1" : "raw",
        head.token_count, (unsigned long long)head.payload_bytes, now_ms() - start_ms,
        read_ms, decompress_ms, validation_ms, copy_ms);
    return 1;
}

static int warm_state_hex_name(NSString *name, NSString *prefix,
                               NSString *suffix) {
    if (![name hasPrefix:prefix] || ![name hasSuffix:suffix] ||
        name.length != prefix.length + 16 + suffix.length) return 0;
    for (NSUInteger i = prefix.length; i < prefix.length + 16; i++) {
        unichar c = [name characterAtIndex:i];
        if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return 0;
    }
    return 1;
}

// Leave active writers alone; abandoned temp files are removed after one hour.
static void warm_state_cleanup_stale_temps(NSString *directory) {
    NSArray<NSString *> *names = [[NSFileManager defaultManager]
        contentsOfDirectoryAtPath:directory error:NULL];
    time_t now = time(NULL);
    for (NSString *name in names) {
        NSRange marker = [name rangeOfString:@".state.tmp."];
        if (marker.location == NSNotFound || NSMaxRange(marker) == name.length) continue;
        NSString *path = [directory stringByAppendingPathComponent:name];
        struct stat st;
        if (lstat(path.fileSystemRepresentation, &st) != 0 ||
            !S_ISREG(st.st_mode) || st.st_mtimespec.tv_sec > now ||
            now - st.st_mtimespec.tv_sec < 3600) continue;
        if (unlink(path.fileSystemRepresentation) == 0)
            fprintf(stderr, "[warm-state] removed stale temporary checkpoint: %s\n",
                    path.fileSystemRepresentation);
    }
}

// The profile is one logical cache slot. Keep its newly saved checkpoint and
// remove older source revisions; files for other profiles are untouched.
static void warm_state_prune_profile(NSString *current_path) {
    NSString *name = current_path.lastPathComponent;
    if (![name hasSuffix:@".state"] || name.length < 24) return;
    NSString *stem = [name substringToIndex:name.length - 23];
    NSString *prefix = [stem stringByAppendingString:@"-"];
    if (!warm_state_hex_name(name, prefix, @".state")) return;
    NSString *directory = [current_path stringByDeletingLastPathComponent];
    struct stat current;
    if (lstat(current_path.fileSystemRepresentation, &current) != 0 ||
        !S_ISREG(current.st_mode)) return;
    NSArray<NSString *> *names = [[NSFileManager defaultManager]
        contentsOfDirectoryAtPath:directory error:NULL];
    for (NSString *candidate in names) {
        if ([candidate isEqualToString:name] ||
            !warm_state_hex_name(candidate, prefix, @".state")) continue;
        NSString *path = [directory stringByAppendingPathComponent:candidate];
        struct stat st;
        if (lstat(path.fileSystemRepresentation, &st) != 0 ||
            !S_ISREG(st.st_mode)) continue;
        if (st.st_mtimespec.tv_sec > current.st_mtimespec.tv_sec ||
            (st.st_mtimespec.tv_sec == current.st_mtimespec.tv_sec &&
             st.st_mtimespec.tv_nsec >= current.st_mtimespec.tv_nsec)) continue;
        if (unlink(path.fileSystemRepresentation) == 0)
            fprintf(stderr, "[warm-state] removed older profile checkpoint: %s\n",
                    path.fileSystemRepresentation);
    }
}

#define WARM_STATE_DISK_BUDGET_BYTES (UINT64_C(4) << 30)

// Bound completed checkpoints across all profiles. Keep the checkpoint just
// published, and evict the oldest regular files with recognized state names.
static void warm_state_prune_to_budget(NSString *directory,
                                       NSString *current_path,
                                       uint64_t budget) {
    NSString *protected_raw = nil;
    NSString *protected_legacy = nil;
    NSString *current_name = current_path.lastPathComponent;
    if ([current_name hasPrefix:@"zstd-"]) {
        NSString *raw_name = [current_name substringFromIndex:5];
        protected_raw = [directory stringByAppendingPathComponent:raw_name];
        current_name = raw_name;
    }
    if ([current_name hasPrefix:@"id2-"])
        protected_legacy = [directory stringByAppendingPathComponent:
            [current_name substringFromIndex:4]];
    NSArray<NSString *> *names = [[NSFileManager defaultManager]
        contentsOfDirectoryAtPath:directory error:NULL];
    NSMutableArray<NSDictionary *> *files = [NSMutableArray array];
    uint64_t total = 0;
    for (NSString *name in names) {
        if (![name hasSuffix:@".state"] || name.length < 24) continue;
        NSString *stem = [name substringToIndex:name.length - 23];
        if (!warm_state_hex_name(name, [stem stringByAppendingString:@"-"], @".state"))
            continue;
        NSString *path = [directory stringByAppendingPathComponent:name];
        struct stat st;
        if (lstat(path.fileSystemRepresentation, &st) != 0 ||
            !S_ISREG(st.st_mode) || st.st_size <= 0) continue;
        uint64_t bytes = (uint64_t)st.st_size;
        total = bytes > UINT64_MAX - total ? UINT64_MAX : total + bytes;
        [files addObject:@{ @"path": path, @"bytes": @(bytes),
            @"seconds": @(st.st_mtimespec.tv_sec),
            @"nanoseconds": @(st.st_mtimespec.tv_nsec) }];
    }
    [files sortUsingComparator:^NSComparisonResult(NSDictionary *a, NSDictionary *b) {
        NSComparisonResult order = [a[@"seconds"] compare:b[@"seconds"]];
        if (order == NSOrderedSame)
            order = [a[@"nanoseconds"] compare:b[@"nanoseconds"]];
        return order == NSOrderedSame ? [a[@"path"] compare:b[@"path"]] : order;
    }];
    for (NSDictionary *file in files) {
        if (total <= budget) break;
        NSString *path = file[@"path"];
        if ([path isEqualToString:current_path] ||
            [path isEqualToString:protected_raw] ||
            [path isEqualToString:protected_legacy]) continue;
        struct stat st;
        if (lstat(path.fileSystemRepresentation, &st) != 0 ||
            !S_ISREG(st.st_mode) || (uint64_t)st.st_size != [file[@"bytes"] unsignedLongLongValue])
            continue;
        if (unlink(path.fileSystemRepresentation) == 0) {
            uint64_t bytes = [file[@"bytes"] unsignedLongLongValue];
            total = total >= bytes ? total - bytes : 0;
            fprintf(stderr, "[warm-state] removed oldest checkpoint for disk budget: %s\n",
                    path.fileSystemRepresentation);
        }
    }
    if (total > budget)
        fprintf(stderr, "[warm-state] WARNING: checkpoint directory exceeds disk budget: %llu/%llu bytes\n",
                (unsigned long long)total, (unsigned long long)budget);
}

static int warm_state_save(NSString *path, const ToolPrefixCacheEntry *entry,
                           KVCache **kv_caches, void **layer_states,
                           uint64_t compatibility, uint64_t source_hash,
                           uint64_t profile_hash) {
    const ServeStateSnapshot *snap = &entry->snapshot;
    if (!snap->valid || snap->pos <= 0) return 0;
    WarmStateHeader head = {0};
    memcpy(head.magic, "FWSTATE1", 8);
    head.version = WARM_STATE_VERSION;
    head.layout_version = WARM_STATE_LAYOUT_VERSION;
    head.header_bytes = sizeof(head);
    head.compatibility = compatibility;
    head.source_hash = source_hash;
    head.profile_hash = profile_hash;
    head.tool_sig = entry->tool_sig;
    head.token_sig = entry->token_sig;
    head.token_count = entry->token_count;
    head.pos = snap->pos;
    head.layers = NUM_LAYERS;
    head.kv_dim = NUM_KV_HEADS * HEAD_DIM;
    head.conv_bytes = (CONV_KERNEL_SIZE-1) * LINEAR_CONV_DIM * sizeof(float);
    head.ssm_bytes = LINEAR_NUM_V_HEADS * LINEAR_VALUE_DIM * LINEAR_KEY_DIM * sizeof(float);
    head.gpu_layers = snapshot_uses_gpu_linear_state() ? g_cfg.num_linear_layers : 0;
    for (int i = 0; i < NUM_LAYERS; i++) head.kv_len[i] = snap->kv_len[i];
    if (!warm_payload_bytes(&head, kv_caches, layer_states,
                            &head.payload_bytes)) return 0;
    if (!warm_state_header_valid(&head, compatibility, source_hash, profile_hash,
                                 kv_caches, layer_states)) return 0;

    uint8_t *compressed = NULL;
    size_t compressed_bytes = 0;
    WarmStateZstdStorage storage = {0};
    if (g_warm_state_zstd_enabled) {
        uint8_t *payload = malloc((size_t)head.payload_bytes);
        if (!payload) return 0;
        int serialized = warm_transfer_snapshot_memory(payload,
            (size_t)head.payload_bytes, (ServeStateSnapshot *)snap, &head,
            kv_caches, layer_states, 1);
        if (!serialized) { free(payload); return 0; }
        head.payload_hash = warm_hash_bytes(UINT64_C(14695981039346656037),
                                            payload, (size_t)head.payload_bytes);
        size_t bound = ZSTD_compressBound((size_t)head.payload_bytes);
        if (bound == 0 || bound > WARM_STATE_MAX_BYTES) { free(payload); return 0; }
        compressed = malloc(bound);
        if (!compressed) { free(payload); return 0; }
        compressed_bytes = ZSTD_compress(compressed, bound, payload,
                                          (size_t)head.payload_bytes, 1);
        free(payload);
        if (ZSTD_isError(compressed_bytes) || compressed_bytes == 0 ||
            compressed_bytes > WARM_STATE_MAX_BYTES) {
            free(compressed); return 0;
        }
        storage.stored_bytes = compressed_bytes;
        storage.stored_hash = warm_hash_bytes(UINT64_C(14695981039346656037),
                                              compressed, compressed_bytes);
        head.version = WARM_STATE_ZSTD_VERSION;
        head.header_bytes = sizeof(head) + sizeof(storage);
    }

    NSString *directory = [path stringByDeletingLastPathComponent];
    if (![[NSFileManager defaultManager] createDirectoryAtPath:directory
            withIntermediateDirectories:YES attributes:nil error:NULL]) {
        free(compressed); return 0;
    }
    warm_state_cleanup_stale_temps(directory);
    NSString *pattern = [path stringByAppendingString:@".tmp.XXXXXX"];
    char *temporary = strdup(pattern.fileSystemRepresentation);
    if (!temporary) { free(compressed); return 0; }
    int fd = mkstemp(temporary);
    if (fd < 0) { free(temporary); free(compressed); return 0; }
    fprintf(stderr, "[warm-state] temporary checkpoint: %s\n", temporary);
    double start_ms = now_ms();
    uint64_t hash = UINT64_C(14695981039346656037);
    int ok;
    if (g_warm_state_zstd_enabled) {
        ok = warm_write_all(fd, &head, sizeof(head), NULL) &&
            warm_write_all(fd, &storage, sizeof(storage), NULL) &&
            warm_write_all(fd, compressed, compressed_bytes, NULL) &&
            fsync(fd) == 0;
    } else {
        ok = warm_write_all(fd, &head, sizeof(head), NULL) &&
            warm_transfer_snapshot(fd, (ServeStateSnapshot *)snap, &head,
                                   kv_caches, layer_states, 1, &hash);
        if (ok) {
            head.payload_hash = hash;
            ok = lseek(fd, 0, SEEK_SET) == 0 &&
                 warm_write_all(fd, &head, sizeof(head), NULL) && fsync(fd) == 0;
        }
    }
    free(compressed);
    if (close(fd) != 0) ok = 0;
    if (ok) {
        fprintf(stderr, "[warm-state] rename %s -> %s\n",
                temporary, path.fileSystemRepresentation);
        ok = rename(temporary, path.fileSystemRepresentation) == 0;
    }
    if (ok) {
        int dir_fd = open(directory.fileSystemRepresentation, O_RDONLY);
        if (dir_fd >= 0) { fsync(dir_fd); close(dir_fd); }
        fprintf(stderr, "[warm-state] saved atomically: format=%s bytes=%llu stored=%llu elapsed=%.0fms path=%s\n",
                head.version == WARM_STATE_ZSTD_VERSION ? "zstd1" : "raw",
                (unsigned long long)head.payload_bytes,
                (unsigned long long)(head.version == WARM_STATE_ZSTD_VERSION
                    ? storage.stored_bytes : head.payload_bytes), now_ms() - start_ms,
                path.fileSystemRepresentation);
        warm_state_prune_profile(path);
        warm_state_prune_to_budget(directory, path, WARM_STATE_DISK_BUDGET_BYTES);
    } else {
        fprintf(stderr, "[warm-state] WARNING: checkpoint save failed: %s\n", strerror(errno));
        unlink(temporary);
    }
    free(temporary);
    return ok;
}

static int warm_state_load_selected(NSString *path, ToolPrefixCacheEntry *entry,
                                    KVCache **kv_caches, void **layer_states,
                                    uint64_t compatibility, uint64_t source_hash,
                                    uint64_t profile_hash,
                                    const ToolPrefixCacheEntry *expected_prefix,
                                    int *repair_compressed) {
    if (repair_compressed) *repair_compressed = 0;
    NSString *current = warm_state_identity_path(path);
    if (!current) return 0;
    NSString *compressed = warm_state_zstd_path(current);
    if (g_warm_state_zstd_enabled) {
        if (compressed && warm_state_load(compressed, entry, kv_caches,
                layer_states, compatibility, source_hash, profile_hash,
                expected_prefix)) return 1;
    } else if (warm_state_load(current, entry, kv_caches, layer_states,
                compatibility, source_hash, profile_hash, expected_prefix)) return 1;
    NSString *fallback = g_warm_state_zstd_enabled ? current : compressed;
    int loaded = fallback && warm_state_load(fallback, entry, kv_caches,
        layer_states, compatibility, source_hash, profile_hash, expected_prefix);
    if (loaded && repair_compressed) *repair_compressed = 1;
    return loaded;
}

static int warm_state_save_selected(NSString *path, const ToolPrefixCacheEntry *entry,
                                    KVCache **kv_caches, void **layer_states,
                                    uint64_t compatibility, uint64_t source_hash,
                                    uint64_t profile_hash) {
    NSString *current = warm_state_identity_path(path);
    NSString *destination = g_warm_state_zstd_enabled ? warm_state_zstd_path(current) : current;
    return destination && warm_state_save(destination, entry, kv_caches,
        layer_states, compatibility, source_hash, profile_hash);
}

static int warm_state_selected_exists(NSString *path) {
    NSString *current = warm_state_identity_path(path);
    NSString *destination = g_warm_state_zstd_enabled ? warm_state_zstd_path(current) : current;
    return destination && access(destination.fileSystemRepresentation, F_OK) == 0;
}

// Exercises the actual disk format and loader without a model or Metal device.
static int warm_state_self_test(const char *directory) {
    int original_compression = g_warm_state_zstd_enabled;
    if (!directory || directory[0] != '/' || mkdir(directory, 0700) != 0) {
        fprintf(stderr, "[warm-state-test] cannot create exclusive directory: %s\n",
                directory ? directory : "(null)");
        return 1;
    }
    fprintf(stderr, "[warm-state-test] directory: %s\n", directory);
    printf("[warm-state-test] default Zstd-1 policy: %s\n",
           original_compression ? "PASS" : "FAIL");
    g_warm_state_zstd_enabled = 0;
    NSString *path = [[NSString stringWithUTF8String:directory]
        stringByAppendingPathComponent:@"snapshot.state"];
    NSString *named_raw = [[NSString stringWithUTF8String:directory]
        stringByAppendingPathComponent:@"flash-test-0000000000000001.state"];
    NSString *named_zstd = warm_state_zstd_path(named_raw);
    int naming_passed = [named_zstd.lastPathComponent
        isEqualToString:@"zstd-flash-test-0000000000000001.state"];
    NSString *identity_name = warm_state_identity_path(named_raw);
    naming_passed = naming_passed && [identity_name.lastPathComponent
        isEqualToString:@"id2-flash-test-0000000000000001.state"];
    printf("[warm-state-test] separate identity and zstd namespaces: %s\n",
           naming_passed ? "PASS" : "FAIL");
    NSString *partial = [path stringByAppendingString:@".tmp.interrupted"];
    KVCache *kv[MAX_LAYERS] = {0};
    void *linear[MAX_LAYERS] = {0};
    linear[0] = (void *)1; // section presence only; data comes from snapshot
    ToolPrefixCacheEntry source = {0}, loaded = {0};
    source.tool_sig = 101;
    uint32_t system_a_ids[] = {11, 22, 33};
    uint32_t system_b_ids[] = {11, 23, 33};
    PromptTokens system_a = {.ids = system_a_ids, .count = 3};
    PromptTokens system_b = {.ids = system_b_ids, .count = 3};
    source.token_sig = prompt_tokens_signature(&system_a);
    source.token_count = 3;
    source.snapshot.pos = 3;
    source.snapshot.valid = 1;
    size_t conv = (CONV_KERNEL_SIZE-1) * LINEAR_CONV_DIM * sizeof(float);
    size_t ssm = LINEAR_NUM_V_HEADS * LINEAR_VALUE_DIM * LINEAR_KEY_DIM * sizeof(float);
    source.snapshot.la_conv_snapshot[0] = malloc(conv);
    source.snapshot.la_ssm_snapshot[0] = malloc(ssm);
    int failures = 0;
    if (!naming_passed) failures++;
    if (!source.snapshot.la_conv_snapshot[0] || !source.snapshot.la_ssm_snapshot[0]) {
        failures++;
        goto cleanup;
    }
    memset(source.snapshot.la_conv_snapshot[0], 0x3a, conv);
    memset(source.snapshot.la_ssm_snapshot[0], 0x5c, ssm);
    uint64_t base_mode = warm_execution_mode_hash(8);
    int saved_gpu_moe = g_gpu_resident_moe_enabled;
    int saved_oproj = g_oproj_v3_enabled;
    int saved_tiny = g_tiny_matvec_fast_enabled;
    int saved_gpu_linear = gpu_linear_attn_enabled;
    int saved_bypass = linear_attn_bypass;
    g_gpu_resident_moe_enabled ^= 1;
    int gpu_mode_changes = warm_execution_mode_hash(8) != base_mode;
    g_gpu_resident_moe_enabled = saved_gpu_moe;
    g_oproj_v3_enabled ^= 1;
    int oproj_mode_changes = warm_execution_mode_hash(8) != base_mode;
    g_oproj_v3_enabled = saved_oproj;
    g_tiny_matvec_fast_enabled ^= 1;
    int tiny_mode_changes = warm_execution_mode_hash(8) != base_mode;
    g_tiny_matvec_fast_enabled = saved_tiny;
    gpu_linear_attn_enabled ^= 1;
    int linear_mode_changes = warm_execution_mode_hash(8) != base_mode;
    gpu_linear_attn_enabled = saved_gpu_linear;
    linear_attn_bypass ^= 1;
    int bypass_mode_changes = warm_execution_mode_hash(8) != base_mode;
    linear_attn_bypass = saved_bypass;
    printf("[warm-state-test] numerical mode changes identity: %s\n",
           gpu_mode_changes && oproj_mode_changes && tiny_mode_changes &&
           linear_mode_changes && bypass_mode_changes ? "PASS" : "FAIL");
    if (!gpu_mode_changes || !oproj_mode_changes || !tiny_mode_changes ||
        !linear_mode_changes || !bypass_mode_changes) failures++;
    if (!warm_state_save(path, &source, kv, linear, 11, 12, 13) ||
        !warm_state_load(path, &loaded, kv, linear, 11, 12, 13, &source)) {
        failures++;
        goto cleanup;
    }
    printf("[warm-state-test] valid restore: PASS\n");
    serve_state_snapshot_free(&loaded.snapshot);
    struct stat st;
    if (stat(path.fileSystemRepresentation, &st) || st.st_size <= (off_t)sizeof(WarmStateHeader)) {
        failures++;
        goto cleanup;
    }
    size_t file_size = (size_t)st.st_size;
    fprintf(stderr, "[warm-state-test] checkpoint file size: %zu bytes\n", file_size);
    uint8_t *original = malloc(file_size);
    if (!original) { failures++; goto cleanup; }
    int fd = open(path.fileSystemRepresentation, O_RDONLY);
    int read_ok = fd >= 0 && warm_read_all(fd, original, file_size, NULL);
    if (fd >= 0) close(fd);
    if (!read_ok) { free(original); failures++; goto cleanup; }

    // The optional representation keeps the original raw checkpoint intact.
    {
    NSString *zstd_path = [[NSString stringWithUTF8String:directory]
        stringByAppendingPathComponent:@"snapshot-zstd.state"];
    g_warm_state_zstd_enabled = 1;
    int zstd_saved = warm_state_save(zstd_path, &source, kv, linear, 11, 12, 13);
    g_warm_state_zstd_enabled = 0;
    int zstd_loaded = zstd_saved && warm_state_load(zstd_path, &loaded,
        kv, linear, 11, 12, 13, &source);
    printf("[warm-state-test] zstd1 round trip: %s\n",
           zstd_loaded ? "PASS" : "FAIL");
    if (!zstd_loaded) failures++;
    serve_state_snapshot_free(&loaded.snapshot);
    NSString *oversized_path = [[NSString stringWithUTF8String:directory]
        stringByAppendingPathComponent:@"oversized-zstd.state"];
    WarmStateHeader compressed_head = {0};
    WarmStateZstdStorage oversized_storage = {0};
    int source_fd = open(zstd_path.fileSystemRepresentation, O_RDONLY | O_NOFOLLOW);
    int oversized_fd = open(oversized_path.fileSystemRepresentation,
        O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW, 0600);
    int oversized_rejected = source_fd >= 0 && oversized_fd >= 0 &&
        warm_read_all(source_fd, &compressed_head, sizeof(compressed_head), NULL) &&
        warm_read_all(source_fd, &oversized_storage, sizeof(oversized_storage), NULL);
    if (oversized_rejected) {
        size_t excess = ZSTD_compressBound((size_t)compressed_head.payload_bytes) + 1;
        oversized_storage.stored_bytes = excess;
        oversized_rejected = excess < WARM_STATE_MAX_BYTES &&
            warm_write_all(oversized_fd, &compressed_head, sizeof(compressed_head), NULL) &&
            warm_write_all(oversized_fd, &oversized_storage, sizeof(oversized_storage), NULL) &&
            ftruncate(oversized_fd, (off_t)(compressed_head.header_bytes + excess)) == 0;
    }
    if (source_fd >= 0) close(source_fd);
    if (oversized_fd >= 0) close(oversized_fd);
    oversized_rejected = oversized_rejected && !warm_state_load(oversized_path,
        &loaded, kv, linear, 11, 12, 13, &source);
    printf("[warm-state-test] oversized Zstd section rejected before allocation: %s\n",
           oversized_rejected ? "PASS" : "FAIL");
    if (!oversized_rejected) failures++;
    unlink(oversized_path.fileSystemRepresentation);
    struct stat zst;
    int zfd = open(zstd_path.fileSystemRepresentation, O_RDWR | O_NOFOLLOW);
    int corrupt_rejected = 0, raw_preserved = 0;
    if (zfd >= 0 && fstat(zfd, &zst) == 0 && zst.st_size >
            (off_t)(sizeof(WarmStateHeader) + sizeof(WarmStateZstdStorage))) {
        uint8_t byte;
        off_t last = zst.st_size - 1;
        if (pread(zfd, &byte, 1, last) == 1) {
            byte ^= 1;
            if (pwrite(zfd, &byte, 1, last) == 1)
                corrupt_rejected = !warm_state_load(zstd_path, &loaded,
                    kv, linear, 11, 12, 13, &source);
        }
    }
    if (zfd >= 0) close(zfd);
    fd = open(path.fileSystemRepresentation, O_RDONLY | O_NOFOLLOW);
    if (fd >= 0) {
        uint8_t *raw = malloc(file_size);
        raw_preserved = raw && warm_read_all(fd, raw, file_size, NULL) &&
            memcmp(raw, original, file_size) == 0;
        free(raw);
        close(fd);
    }
    printf("[warm-state-test] compressed corruption rejected, raw preserved: %s\n",
           corrupt_rejected && raw_preserved ? "PASS" : "FAIL");
    if (!corrupt_rejected || !raw_preserved) failures++;
    unlink(zstd_path.fileSystemRepresentation);
    }

    {
        NSString *new_raw = warm_state_identity_path(named_raw);
        NSString *new_zstd = warm_state_zstd_path(new_raw);
        int repair = 0;
        int repaired = warm_state_save_selected(named_raw, &source, kv, linear,
                                               11, 12, 13);
        WarmStateHeader raw_head = {0}, zstd_head = {0};
        int raw_fd = repaired ? open(new_raw.fileSystemRepresentation, O_RDONLY | O_NOFOLLOW) : -1;
        int raw_format = raw_fd >= 0 && warm_read_all(raw_fd, &raw_head,
            sizeof(raw_head), NULL) && raw_head.version == WARM_STATE_VERSION;
        if (raw_fd >= 0) close(raw_fd);
        printf("[warm-state-test] explicit raw save format: %s\n",
               raw_format ? "PASS" : "FAIL");
        if (!raw_format) failures++;
        g_warm_state_zstd_enabled = 1;
        repaired = repaired && warm_state_save_selected(named_raw, &source,
            kv, linear, 11, 12, 13);
        int zstd_fd = repaired ? open(new_zstd.fileSystemRepresentation, O_RDONLY | O_NOFOLLOW) : -1;
        int default_format = zstd_fd >= 0 && warm_read_all(zstd_fd, &zstd_head,
            sizeof(zstd_head), NULL) && zstd_head.version == WARM_STATE_ZSTD_VERSION;
        if (zstd_fd >= 0) close(zstd_fd);
        printf("[warm-state-test] default Zstd-1 save format: %s\n",
               default_format ? "PASS" : "FAIL");
        if (!default_format) failures++;
        int zfd = repaired ? open(new_zstd.fileSystemRepresentation,
                                   O_RDWR | O_NOFOLLOW) : -1;
        if (zfd >= 0) {
            unsigned char byte = 0;
            off_t end = lseek(zfd, 0, SEEK_END);
            if (end > (off_t)sizeof(WarmStateHeader) &&
                pread(zfd, &byte, 1, end - 1) == 1) {
                byte ^= 1;
                repaired = pwrite(zfd, &byte, 1, end - 1) == 1;
            } else repaired = 0;
            close(zfd);
        } else repaired = 0;
        repaired = repaired && warm_state_load_selected(named_raw, &loaded,
            kv, linear, 11, 12, 13, &source, &repair) && repair;
        serve_state_snapshot_free(&loaded.snapshot);
        repaired = repaired && warm_state_save_selected(named_raw, &source,
            kv, linear, 11, 12, 13);
        repair = 0;
        repaired = repaired && warm_state_load_selected(named_raw, &loaded,
            kv, linear, 11, 12, 13, &source, &repair) && !repair;
        serve_state_snapshot_free(&loaded.snapshot);
        g_warm_state_zstd_enabled = 0;
        printf("[warm-state-test] damaged zstd fallback and repair: %s\n",
               repaired ? "PASS" : "FAIL");
        if (!repaired) failures++;
        unlink(new_zstd.fileSystemRepresentation);
        unlink(new_raw.fileSystemRepresentation);
    }

    const char *labels[] = {"wrong magic", "wrong format", "wrong layout",
        "oversized token count", "altered payload length", "altered dimensions",
        "payload checksum", "truncated file", "extra payload",
        "wrong payload checksum", "wrong token position", "missing token signature"};
    for (int case_index = 0; case_index < 12; case_index++) {
        uint8_t *mutated = malloc(file_size + 1);
        if (!mutated) { failures++; break; }
        memcpy(mutated, original, file_size);
        WarmStateHeader *header = (WarmStateHeader *)mutated;
        size_t bytes = file_size;
        switch (case_index) {
            case 0: header->magic[0] ^= 1; break;
            case 1: header->version++; break;
            case 2: header->layout_version++; break;
            case 3: header->token_count = TOOL_PREFIX_CACHE_MAX_TOKENS + 1; break;
            case 4: header->payload_bytes++; break;
            case 5: header->conv_bytes++; break;
            case 6: mutated[sizeof(WarmStateHeader)] ^= 1; break;
            case 7: bytes--; break;
            case 8: mutated[bytes++] = 0; break;
            case 9: header->payload_hash ^= 1; break;
            case 10: header->pos++; break;
            case 11: header->token_sig = 0; break;
        }
        fd = open(path.fileSystemRepresentation, O_WRONLY | O_TRUNC);
        int written = fd >= 0 && warm_write_all(fd, mutated, bytes, NULL);
        if (fd >= 0) close(fd);
        int rejected = written && !warm_state_load(path, &loaded, kv, linear, 11, 12, 13, &source);
        printf("[warm-state-test] %s: %s\n", labels[case_index], rejected ? "PASS" : "FAIL");
        if (!rejected) failures++;
        serve_state_snapshot_free(&loaded.snapshot);
        free(mutated);
    }
    // The same valid file must reject changed model, source/profile, or tokenizer identity.
    fd = open(path.fileSystemRepresentation, O_WRONLY | O_TRUNC);
    int restored = fd >= 0 && warm_write_all(fd, original, file_size, NULL);
    if (fd >= 0) close(fd);
    free(original);
    int identities_reject = restored &&
        !warm_state_load(path, &loaded, kv, linear, 14, 12, 13, &source) &&
        !warm_state_load(path, &loaded, kv, linear, 11, 14, 13, &source) &&
        !warm_state_load(path, &loaded, kv, linear, 11, 12, 14, &source);
    printf("[warm-state-test] changed identity/source/profile: %s\n",
           identities_reject ? "PASS" : "FAIL");
    if (!identities_reject) failures++;
    ToolPrefixCacheEntry different_prefix = source;
    different_prefix.token_sig = prompt_tokens_signature(&system_b);
    int prefix_rejected = !warm_state_load(path, &loaded, kv, linear,
                                            11, 12, 13, &different_prefix);
    printf("[warm-state-test] valid checkpoint, different system-prefix tokens: %s\n",
           prefix_rejected ? "PASS" : "FAIL");
    if (!prefix_rejected) failures++;
    // A partial temp file must leave the final checkpoint intact.
    fd = open(partial.fileSystemRepresentation, O_CREAT | O_TRUNC | O_WRONLY, 0600);
    fprintf(stderr, "[warm-state-test] interrupted temp path: %s\n",
            partial.fileSystemRepresentation);
    if (fd >= 0) { warm_write_all(fd, "incomplete", 10, NULL); close(fd); }
    int survived = warm_state_load(path, &loaded, kv, linear, 11, 12, 13, &source);
    printf("[warm-state-test] interrupted write leaves final valid: %s\n",
           survived ? "PASS" : "FAIL");
    if (!survived) failures++;
    serve_state_snapshot_free(&loaded.snapshot);
    unlink(partial.fileSystemRepresentation);
    // A failed load falls back to rebuild, then the replacement loads.
    fd = open(path.fileSystemRepresentation, O_WRONLY | O_TRUNC);
    if (fd >= 0) { warm_write_all(fd, "bad", 3, NULL); close(fd); }
    int rebuilt = !warm_state_load(path, &loaded, kv, linear, 11, 12, 13, &source) &&
        warm_state_save(path, &source, kv, linear, 11, 12, 13) &&
        warm_state_load(path, &loaded, kv, linear, 11, 12, 13, &source);
    printf("[warm-state-test] corrupt file rebuild: %s\n", rebuilt ? "PASS" : "FAIL");
    if (!rebuilt) failures++;

    {
    NSString *identity_file = [[NSString stringWithUTF8String:directory]
        stringByAppendingPathComponent:@"identity.json"];
    [@"a" writeToFile:identity_file atomically:YES encoding:NSUTF8StringEncoding error:NULL];
    struct stat identity_stat;
    int identity_statted = stat(identity_file.fileSystemRepresentation, &identity_stat) == 0;
    uint64_t before_hash = UINT64_C(14695981039346656037);
    int before_hashed = warm_hash_small_file(&before_hash, identity_file.fileSystemRepresentation);
    [@"b" writeToFile:identity_file atomically:YES encoding:NSUTF8StringEncoding error:NULL];
    if (identity_statted) {
        struct timeval times[2] = {
            {identity_stat.st_atimespec.tv_sec, identity_stat.st_atimespec.tv_nsec / 1000},
            {identity_stat.st_mtimespec.tv_sec, identity_stat.st_mtimespec.tv_nsec / 1000}};
        utimes(identity_file.fileSystemRepresentation, times);
    }
    uint64_t after_hash = UINT64_C(14695981039346656037);
    int after_hashed = warm_hash_small_file(&after_hash, identity_file.fileSystemRepresentation);
    int content_rejected = identity_statted && before_hashed && after_hashed &&
        before_hash != after_hash;
    printf("[warm-state-test] metadata content changes identity: %s\n",
           content_rejected ? "PASS" : "FAIL");
    if (!content_rejected) failures++;
    uint64_t new_a = UINT64_C(14695981039346656037);
    uint64_t new_b = new_a, legacy_a = new_a, legacy_b = new_a;
    uint64_t device = identity_statted ? (uint64_t)identity_stat.st_dev : 1;
    int device_policy = warm_hash_stat_identity(&new_a,
            identity_file.fileSystemRepresentation, 0, device) &&
        warm_hash_stat_identity(&new_b,
            identity_file.fileSystemRepresentation, 0, device + 1) &&
        warm_hash_stat_identity(&legacy_a,
            identity_file.fileSystemRepresentation, 1, device) &&
        warm_hash_stat_identity(&legacy_b,
            identity_file.fileSystemRepresentation, 1, device + 1) &&
        new_a == new_b && legacy_a != legacy_b;
    printf("[warm-state-test] device ID excluded only from new identity: %s\n",
           device_policy ? "PASS" : "FAIL");
    if (!device_policy) failures++;
    unlink(identity_file.fileSystemRepresentation);

    NSString *test_directory = [NSString stringWithUTF8String:directory];
    NSString *old_profile = [test_directory stringByAppendingPathComponent:
        @"dsh-test-0000000000000001.state"];
    NSString *new_profile = [test_directory stringByAppendingPathComponent:
        @"dsh-test-0000000000000002.state"];
    NSString *other_profile = [test_directory stringByAppendingPathComponent:
        @"dsh-other-0000000000000001.state"];
    NSString *old_temp = [test_directory stringByAppendingPathComponent:
        @"dsh-test-0000000000000002.state.tmp.ABCDEF"];
    NSString *fresh_temp = [test_directory stringByAppendingPathComponent:
        @"dsh-test-0000000000000002.state.tmp.GHIJKL"];
    for (NSString *file in @[old_profile, new_profile, other_profile, old_temp, fresh_temp])
        [@"x" writeToFile:file atomically:YES encoding:NSUTF8StringEncoding error:NULL];
    time_t now = time(NULL);
    struct timeval old_times[2] = {{now - 7200, 0}, {now - 7200, 0}};
    utimes(old_profile.fileSystemRepresentation, old_times);
    utimes(old_temp.fileSystemRepresentation, old_times);
    warm_state_cleanup_stale_temps(test_directory);
    warm_state_prune_profile(new_profile);
    int cleanup_passed = access(old_profile.fileSystemRepresentation, F_OK) != 0 &&
        access(old_temp.fileSystemRepresentation, F_OK) != 0 &&
        access(new_profile.fileSystemRepresentation, F_OK) == 0 &&
        access(other_profile.fileSystemRepresentation, F_OK) == 0 &&
        access(fresh_temp.fileSystemRepresentation, F_OK) == 0;
    printf("[warm-state-test] profile and stale-temp cleanup: %s\n",
           cleanup_passed ? "PASS" : "FAIL");
    if (!cleanup_passed) failures++;
    for (NSString *file in @[old_profile, new_profile, other_profile, old_temp, fresh_temp])
        unlink(file.fileSystemRepresentation);
    }
cleanup:
    g_warm_state_zstd_enabled = original_compression;
    serve_state_snapshot_free(&loaded.snapshot);
    serve_state_snapshot_free(&source.snapshot);
    unlink(path.fileSystemRepresentation);
    rmdir(directory);
    printf("[warm-state-test] RESULT: %s\n", failures ? "FAIL" : "PASS");
    return failures ? 1 : 0;
}
