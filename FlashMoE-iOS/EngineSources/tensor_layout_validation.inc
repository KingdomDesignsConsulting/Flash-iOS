// Validate native Qwen3.5 tensor storage before any layer pointer/cache or
// Metal weight buffer can consume it. Expert files have a separate layout.
static int native_tensor_expected(WeightFile *wf, const char *name,
                                  const char *dtype, int ndim,
                                  int d0, int d1, int d2) {
    TensorInfo *t = get_tensor_info(wf, name);
    if (!t) return 1; // Existing required-tensor check handles absent overlays.
    int dims[3] = {d0, d1, d2};
    size_t elements = 1;
    for (int i = 0; i < ndim; i++) {
        if (dims[i] <= 0 || elements > SIZE_MAX / (size_t)dims[i]) return 0;
        elements *= (size_t)dims[i];
    }
    size_t width = strcmp(dtype, "U32") == 0 || strcmp(dtype, "F32") == 0 ? 4 : 2;
    if (elements > SIZE_MAX / width) return 0;
    size_t expected_bytes = elements * width;
    int valid = strcmp(t->dtype, dtype) == 0 && t->ndim == ndim &&
        t->size == expected_bytes && t->offset <= wf->size &&
        t->size <= wf->size - t->offset;
    for (int i = 0; i < ndim && valid; i++) valid = t->shape[i] == dims[i];
    if (!valid) {
        fprintf(stderr, "ERROR: tensor layout %s: expected %s [%d,%d,%d] "
                "ndim=%d bytes=%zu; got %s [%d,%d,%d] ndim=%d bytes=%zu\n",
                name, dtype, d0, d1, d2, ndim, expected_bytes,
                t->dtype, t->shape[0], t->shape[1], t->shape[2], t->ndim, t->size);
    }
    return valid;
}

static int native_vector_expected(WeightFile *wf, const char *name,
                                  const char *dtype, int length) {
    return native_tensor_expected(wf, name, dtype, 1, length, 0, 0);
}

static int native_triplet_expected(WeightFile *wf, const char *base,
                                   int out_dim, int in_dim) {
    if (in_dim <= 0 || in_dim % GROUP_SIZE != 0 || in_dim % 8 != 0) return 0;
    char name[224];
    snprintf(name, sizeof(name), "%s.weight", base);
    if (!native_tensor_expected(wf, name, "U32", 2, out_dim, in_dim / 8, 0)) return 0;
    snprintf(name, sizeof(name), "%s.scales", base);
    if (!native_tensor_expected(wf, name, "BF16", 2,
                                out_dim, in_dim / GROUP_SIZE, 0)) return 0;
    snprintf(name, sizeof(name), "%s.biases", base);
    return native_tensor_expected(wf, name, "BF16", 2,
                                  out_dim, in_dim / GROUP_SIZE, 0);
}

static int validate_native_tensor_layout(WeightFile *wf) {
    if (!wf || !wf->manifest) return 0;
    // Every declared native tensor must describe the bytes its dtype/shape
    // actually occupies, even if a GGUF overlay selects another source.
    for (int i = 0; i < wf->manifest->num_tensors; i++) {
        TensorInfo *t = &wf->manifest->tensors[i];
        size_t width = strcmp(t->dtype, "BF16") == 0 ? 2 :
            (strcmp(t->dtype, "F32") == 0 || strcmp(t->dtype, "U32") == 0) ? 4 : 0;
        if (!width || t->ndim < 1 || t->ndim > 4) {
            fprintf(stderr, "ERROR: tensor %s has unsupported dtype/rank\n", t->name);
            return 0;
        }
        size_t count = 1;
        for (int j = 0; j < t->ndim; j++) {
            if (t->shape[j] <= 0 || count > SIZE_MAX / (size_t)t->shape[j]) return 0;
            count *= (size_t)t->shape[j];
        }
        if (count > SIZE_MAX / width || t->size != count * width) {
            fprintf(stderr, "ERROR: tensor %s declared size disagrees with dtype/shape\n",
                    t->name);
            return 0;
        }
    }
    if (!native_vector_expected(wf, "model.norm.weight", "BF16", HIDDEN_DIM) ||
        !native_triplet_expected(wf, "model.embed_tokens", VOCAB_SIZE, HIDDEN_DIM) ||
        !native_triplet_expected(wf, "lm_head", VOCAB_SIZE, HIDDEN_DIM)) return 0;
    char base[224];
    for (int layer = 0; layer < NUM_LAYERS; layer++) {
        snprintf(base, sizeof(base), "model.layers.%d.input_layernorm.weight", layer);
        if (!native_vector_expected(wf, base, "BF16", HIDDEN_DIM)) return 0;
        snprintf(base, sizeof(base), "model.layers.%d.post_attention_layernorm.weight", layer);
        if (!native_vector_expected(wf, base, "BF16", HIDDEN_DIM)) return 0;
#define CHECK_TRIPLET(suffix, out, in) do { \
    snprintf(base, sizeof(base), "model.layers.%d." suffix, layer); \
    if (!native_triplet_expected(wf, base, (out), (in))) return 0; \
} while (0)
#define CHECK_VECTOR(suffix, dtype, len) do { \
    snprintf(base, sizeof(base), "model.layers.%d." suffix, layer); \
    if (!native_vector_expected(wf, base, dtype, (len))) return 0; \
} while (0)
        CHECK_TRIPLET("mlp.gate", NUM_EXPERTS, HIDDEN_DIM);
        CHECK_TRIPLET("mlp.shared_expert.gate_proj", SHARED_INTERMEDIATE, HIDDEN_DIM);
        CHECK_TRIPLET("mlp.shared_expert.up_proj", SHARED_INTERMEDIATE, HIDDEN_DIM);
        CHECK_TRIPLET("mlp.shared_expert.down_proj", HIDDEN_DIM, SHARED_INTERMEDIATE);
        CHECK_TRIPLET("mlp.shared_expert_gate", 1, HIDDEN_DIM);
        if ((layer + 1) % FULL_ATTN_INTERVAL == 0) {
            CHECK_TRIPLET("self_attn.q_proj", 2 * NUM_ATTN_HEADS * HEAD_DIM, HIDDEN_DIM);
            CHECK_TRIPLET("self_attn.k_proj", NUM_KV_HEADS * HEAD_DIM, HIDDEN_DIM);
            CHECK_TRIPLET("self_attn.v_proj", NUM_KV_HEADS * HEAD_DIM, HIDDEN_DIM);
            CHECK_TRIPLET("self_attn.o_proj", HIDDEN_DIM, NUM_ATTN_HEADS * HEAD_DIM);
            CHECK_VECTOR("self_attn.q_norm.weight", "BF16", HEAD_DIM);
            CHECK_VECTOR("self_attn.k_norm.weight", "BF16", HEAD_DIM);
        } else {
            CHECK_TRIPLET("linear_attn.in_proj_qkv", LINEAR_CONV_DIM, HIDDEN_DIM);
            CHECK_TRIPLET("linear_attn.in_proj_z", LINEAR_TOTAL_VALUE, HIDDEN_DIM);
            CHECK_TRIPLET("linear_attn.in_proj_b", LINEAR_NUM_V_HEADS, HIDDEN_DIM);
            CHECK_TRIPLET("linear_attn.in_proj_a", LINEAR_NUM_V_HEADS, HIDDEN_DIM);
            CHECK_TRIPLET("linear_attn.out_proj", HIDDEN_DIM, LINEAR_TOTAL_VALUE);
            CHECK_VECTOR("linear_attn.A_log", "F32", LINEAR_NUM_V_HEADS);
            CHECK_VECTOR("linear_attn.dt_bias", "BF16", LINEAR_NUM_V_HEADS);
            CHECK_VECTOR("linear_attn.norm.weight", "BF16", LINEAR_VALUE_DIM);
            snprintf(base, sizeof(base), "model.layers.%d.linear_attn.conv1d.weight", layer);
            if (!native_tensor_expected(wf, base, "BF16", 3,
                                        LINEAR_CONV_DIM, CONV_KERNEL_SIZE, 1)) return 0;
        }
#undef CHECK_TRIPLET
#undef CHECK_VECTOR
    }
    return 1;
}

static int run_native_tensor_layout_self_tests(void) {
    TensorInfo tensor = { .name = "model.norm.weight", .offset = 0,
        .size = (size_t)HIDDEN_DIM * 2, .ndim = 1,
        .shape = { HIDDEN_DIM } };
    strcpy(tensor.dtype, "BF16");
    TensorManifest manifest = { .tensors = &tensor, .num_tensors = 1, .capacity = 1 };
    WeightFile wf = { .size = (size_t)HIDDEN_DIM * 4, .manifest = &manifest };
    tensor_ht_built = 0;
    int good = validate_native_tensor_layout(&wf);
    strcpy(tensor.dtype, "F32");
    tensor.size = (size_t)HIDDEN_DIM * 4;
    tensor_ht_built = 0;
    int wrong_dtype = !validate_native_tensor_layout(&wf);
    strcpy(tensor.dtype, "BF16");
    tensor.shape[0] = HIDDEN_DIM / 2;
    tensor.size = (size_t)tensor.shape[0] * 2;
    tensor_ht_built = 0;
    int wrong_dimension = !validate_native_tensor_layout(&wf);
    tensor.shape[0] = HIDDEN_DIM;
    tensor.size = (size_t)HIDDEN_DIM;
    tensor_ht_built = 0;
    int undersized = !validate_native_tensor_layout(&wf);
    tensor.shape[0] = HIDDEN_DIM / 2;
    tensor.size = (size_t)tensor.shape[0] * 2;
    tensor.offset = wf.size - tensor.size;
    tensor_ht_built = 0;
    int in_bounds_wrong_geometry = !validate_native_tensor_layout(&wf);
    tensor_ht_built = 0;
    int passed = good && wrong_dtype && wrong_dimension && undersized &&
        in_bounds_wrong_geometry;
    printf("[tensor-layout-self-test] dtype/dimension/size/in-bounds geometry: %s\n",
           passed ? "PASS" : "FAIL");
    return passed ? 0 : 1;
}
