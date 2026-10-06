# Makefile for metal_infer — Pure C/Metal MoE inference engine
#
# Targets:
#   make          — build metal_infer binary
#   make run      — single expert forward pass
#   make verify   — verify Metal vs CPU reference
#   make bench    — benchmark single expert (10 iterations)
#   make moe      — full MoE forward pass (K experts, single layer)
#   make moebench — benchmark MoE (10 iterations)
#   make full     — full 60-layer MoE forward pass (K=4)
#   make fullbench — benchmark full 60-layer forward (3 iterations)
#   make chat     — build interactive chat TUI
#   make clean    — remove build artifacts
#
# Note: Metal shaders are compiled from source at runtime via
# MTLDevice newLibraryWithSource:, so no offline metal compiler needed.

CC = clang
CFLAGS = -O2 -Wall -Wextra -fobjc-arc -DACCELERATE_NEW_LAPACK
FRAMEWORKS = -framework Metal -framework Foundation -framework Accelerate
LDFLAGS = -lpthread -lcompression -L/opt/homebrew/lib -lzstd
CFLAGS += -I/opt/homebrew/include

TARGET = metal_infer
MAIN_SRC = main.m

# Optional: offline shader compilation (faster startup, but not required)
METALC = xcrun -sdk macosx metal
METALLIB_TOOL = xcrun -sdk macosx metallib
SHADER_SRC = shaders.metal
SHADER_AIR = shaders.air
SHADER_LIB = shaders.metallib

# Inference engine (complete forward pass)
INFER_TARGET = infer
INFER_SRC = infer.m
# Accepted production prefill: N128 + M4-8row fixed-bit Q4/Q2 gate/up (bitsplit) + M4-2row down.
# --no-prefill-nrow keeps the established scalar prefill available at runtime.
INFER_CFLAGS = $(CFLAGS) -DFLASH_PREFILL_NROW_PRODUCTION -DFLASH_PREFILL_NROW_ASYNC -DFLASH_PREFILL_NROW_GATEUP_M4_8ROW_BITSPLIT

# Chat TUI (interactive multi-turn)
CHAT_TARGET = chat
CHAT_SRC = chat.m

.PHONY: all clean run verify bench moe moebench full fullbench fast metallib infer-run chat-run build-chat n128bench n128gateup8 n128gateup4row n128gateup8row n128gateup8cache n128gateup8bits n128downbits n128gateup16row n128serve8row n128serve8bits

all: $(TARGET) $(INFER_TARGET)

# Build the binary (shaders compiled at runtime from source)
$(TARGET): $(MAIN_SRC) $(SHADER_SRC)
	$(CC) $(CFLAGS) $(FRAMEWORKS) $(LDFLAGS) $(MAIN_SRC) -o $(TARGET)

# Optional: pre-compile shaders (not required — runtime compilation is the default)
metallib: $(SHADER_LIB)

$(SHADER_AIR): $(SHADER_SRC)
	$(METALC) -c $(SHADER_SRC) -o $(SHADER_AIR)

$(SHADER_LIB): $(SHADER_AIR)
	$(METALLIB_TOOL) $(SHADER_AIR) -o $(SHADER_LIB)

# Build the inference engine. Keep direct source includes as prerequisites so
# incremental builds cannot silently retain stale validation/runtime code.
INFER_DEPS = gguf_iq_shared.h tensor_layout_validation.inc tokenizer.h warm_state_cache.inc \
	target_verify_bench.inc target_verify_batch.inc target_verify_grouped.inc \
	prefill_nrow_grouped_async.inc prefill_nrow_control.inc \
	prefill_probe/chunk_kernels.metal
$(INFER_TARGET): $(INFER_SRC) $(INFER_DEPS)
	$(CC) $(INFER_CFLAGS) $(FRAMEWORKS) $(LDFLAGS) $(INFER_SRC) -o $(INFER_TARGET)

# Experimental N128 prefill benchmark. This does NOT replace or rebuild the
# production infer binary. It widens only the benchmark slab while retaining
# the former M4-2row gate+up/down control. Production is N128 with M4-8row bitsplit gate+up and M4-2row down.
N128_BENCH_TARGET = ../Testing/Temporary Testing Files/Apps/infer-n128-bench
N128_BENCH_CFLAGS = $(CFLAGS) \
	-DFLASH_PREFILL_NROW_BENCH \
	-DFLASH_PREFILL_NROW_ASYNC \
	-DFLASH_PREFILL_NROW_N128 \
	-DFLASH_PREFILL_NROW_1K_1024 \
	-DFLASH_PREFILL_NROW_DOWN_M4_2ROW \
	-DFLASH_PREFILL_NROW_GATEUP_M4_2ROW \
	-DFLASH_PREFILL_NROW_EXPERT_PHASE_TIMING

n128bench: $(INFER_SRC) $(INFER_DEPS)
	$(CC) $(N128_BENCH_CFLAGS) $(FRAMEWORKS) $(LDFLAGS) $(INFER_SRC) -o "$(N128_BENCH_TARGET)"
	@echo "Built benchmark-only $(N128_BENCH_TARGET); production ./$(INFER_TARGET) was not replaced."

# Experimental N128 gate+up M8 candidate. Routed down remains the accepted
# M4-2row kernel; only routed gate+up changes from M4 to M8.
N128_GATEUP8_TARGET = ../Testing/Temporary Testing Files/Apps/infer-n128-gateup-m8-bench
N128_GATEUP8_CFLAGS = $(CFLAGS) \
	-DFLASH_PREFILL_NROW_BENCH \
	-DFLASH_PREFILL_NROW_ASYNC \
	-DFLASH_PREFILL_NROW_N128 \
	-DFLASH_PREFILL_NROW_1K_1024 \
	-DFLASH_PREFILL_NROW_DOWN_M4_2ROW \
	-DFLASH_PREFILL_NROW_GATEUP_M8_2ROW \
	-DFLASH_PREFILL_NROW_EXPERT_PHASE_TIMING

n128gateup8: $(INFER_SRC) $(INFER_DEPS)
	$(CC) $(N128_GATEUP8_CFLAGS) $(FRAMEWORKS) $(LDFLAGS) $(INFER_SRC) -o "$(N128_GATEUP8_TARGET)"
	@echo "Built benchmark-only $(N128_GATEUP8_TARGET); production ./$(INFER_TARGET) and N128 M4 control were not replaced."

# Experimental N128 gate+up M4-4row candidate. Routed down remains M4-2row;
# gate+up retains M4 arithmetic and changes only threadgroup packing 2 -> 4 rows.
N128_GATEUP4ROW_TARGET = ../Testing/Temporary Testing Files/Apps/infer-n128-gateup-m4-4row-bench
N128_GATEUP4ROW_CFLAGS = $(CFLAGS) \
	-DFLASH_PREFILL_NROW_BENCH \
	-DFLASH_PREFILL_NROW_ASYNC \
	-DFLASH_PREFILL_NROW_N128 \
	-DFLASH_PREFILL_NROW_1K_1024 \
	-DFLASH_PREFILL_NROW_DOWN_M4_2ROW \
	-DFLASH_PREFILL_NROW_GATEUP_M4_4ROW \
	-DFLASH_PREFILL_NROW_EXPERT_PHASE_TIMING

n128gateup4row: $(INFER_SRC) $(INFER_DEPS)
	$(CC) $(N128_GATEUP4ROW_CFLAGS) $(FRAMEWORKS) $(LDFLAGS) $(INFER_SRC) -o "$(N128_GATEUP4ROW_TARGET)"
	@echo "Built benchmark-only $(N128_GATEUP4ROW_TARGET); production ./$(INFER_TARGET), N128 M4 control, and M8 diagnostic were not replaced."

# Experimental N128 gate+up M4-8row candidate. Routed down remains M4-2row;
# gate+up retains M4 arithmetic and changes only threadgroup packing 4 -> 8 rows.
N128_GATEUP8ROW_TARGET = ../Testing/Temporary Testing Files/Apps/infer-n128-gateup-m4-8row-bench
N128_GATEUP8ROW_CFLAGS = $(CFLAGS) \
	-DFLASH_PREFILL_NROW_BENCH \
	-DFLASH_PREFILL_NROW_ASYNC \
	-DFLASH_PREFILL_NROW_N128 \
	-DFLASH_PREFILL_NROW_1K_1024 \
	-DFLASH_PREFILL_NROW_DOWN_M4_2ROW \
	-DFLASH_PREFILL_NROW_GATEUP_M4_8ROW \
	-DFLASH_PREFILL_NROW_EXPERT_PHASE_TIMING

n128gateup8row: $(INFER_SRC) $(INFER_DEPS)
	$(CC) $(N128_GATEUP8ROW_CFLAGS) $(FRAMEWORKS) $(LDFLAGS) $(INFER_SRC) -o "$(N128_GATEUP8ROW_TARGET)"
	@echo "Built benchmark-only $(N128_GATEUP8ROW_TARGET); production ./$(INFER_TARGET) and prior N128 candidates were not replaced."

# Experimental N128 gate+up M4-8row shared-input-cache candidate.
# Arithmetic and accepted row packing remain M4-8row; four routed input rows
# are cooperatively cached in an 8 KiB threadgroup tile and reused by all
# eight SIMD groups.
N128_GATEUP8CACHE_TARGET = ../Testing/Temporary Testing Files/Apps/infer-n128-gateup-m4-8row-xcache-bench
N128_GATEUP8CACHE_CFLAGS = $(CFLAGS) \
	-DFLASH_PREFILL_NROW_BENCH \
	-DFLASH_PREFILL_NROW_ASYNC \
	-DFLASH_PREFILL_NROW_N128 \
	-DFLASH_PREFILL_NROW_1K_1024 \
	-DFLASH_PREFILL_NROW_DOWN_M4_2ROW \
	-DFLASH_PREFILL_NROW_GATEUP_M4_8ROW_XCACHE \
	-DFLASH_PREFILL_NROW_EXPERT_PHASE_TIMING

n128gateup8cache: $(INFER_SRC) $(INFER_DEPS)
	$(CC) $(N128_GATEUP8CACHE_CFLAGS) $(FRAMEWORKS) $(LDFLAGS) $(INFER_SRC) -o "$(N128_GATEUP8CACHE_TARGET)"
	@echo "Built benchmark-only $(N128_GATEUP8CACHE_TARGET); production ./$(INFER_TARGET) was not replaced."

# Experimental N128 gate+up M4-8row fixed-bit decode candidate.
# Keeps accepted M4-8row geometry but selects dedicated Q4/Q2 pipelines so
# the Metal compiler sees constant unpack width, mask, and shift stride.
N128_GATEUP8BITS_TARGET = ../Testing/Temporary Testing Files/Apps/infer-n128-gateup-m4-8row-bitsplit-bench
N128_GATEUP8BITS_CFLAGS = $(CFLAGS) \
	-DFLASH_PREFILL_NROW_BENCH \
	-DFLASH_PREFILL_NROW_ASYNC \
	-DFLASH_PREFILL_NROW_N128 \
	-DFLASH_PREFILL_NROW_1K_1024 \
	-DFLASH_PREFILL_NROW_DOWN_M4_2ROW \
	-DFLASH_PREFILL_NROW_GATEUP_M4_8ROW_BITSPLIT \
	-DFLASH_PREFILL_NROW_EXPERT_PHASE_TIMING

n128gateup8bits: $(INFER_SRC) $(INFER_DEPS)
	$(CC) $(N128_GATEUP8BITS_CFLAGS) $(FRAMEWORKS) $(LDFLAGS) $(INFER_SRC) -o "$(N128_GATEUP8BITS_TARGET)"
	@echo "Built benchmark-only $(N128_GATEUP8BITS_TARGET); production ./$(INFER_TARGET) was not replaced."

# Experimental N128 routed-down fixed-bit decode candidate. Gate+up stays on
# the production M4-8row Q4/Q2 bitsplit path; only accepted M4-2row down changes
# from dynamic bit-width decode to dedicated Q4/Q2 pipelines.
N128_DOWNBITS_TARGET = ../Testing/Temporary Testing Files/Apps/infer-n128-down-m4-2row-bitsplit-bench
N128_DOWNBITS_CFLAGS = $(CFLAGS) \
	-DFLASH_PREFILL_NROW_BENCH \
	-DFLASH_PREFILL_NROW_ASYNC \
	-DFLASH_PREFILL_NROW_N128 \
	-DFLASH_PREFILL_NROW_1K_1024 \
	-DFLASH_PREFILL_NROW_DOWN_M4_2ROW_BITSPLIT \
	-DFLASH_PREFILL_NROW_GATEUP_M4_8ROW_BITSPLIT \
	-DFLASH_PREFILL_NROW_EXPERT_PHASE_TIMING

n128downbits: $(INFER_SRC) $(INFER_DEPS)
	$(CC) $(N128_DOWNBITS_CFLAGS) $(FRAMEWORKS) $(LDFLAGS) $(INFER_SRC) -o "$(N128_DOWNBITS_TARGET)"
	@echo "Built benchmark-only $(N128_DOWNBITS_TARGET); production ./$(INFER_TARGET) was not replaced."

# Experimental N128 gate+up M4-16row candidate. Routed down remains M4-2row;
# gate+up retains M4 arithmetic and changes only threadgroup packing 8 -> 16 rows.
N128_GATEUP16ROW_TARGET = ../Testing/Temporary Testing Files/Apps/infer-n128-gateup-m4-16row-bench
N128_GATEUP16ROW_CFLAGS = $(CFLAGS) \
	-DFLASH_PREFILL_NROW_BENCH \
	-DFLASH_PREFILL_NROW_ASYNC \
	-DFLASH_PREFILL_NROW_N128 \
	-DFLASH_PREFILL_NROW_1K_1024 \
	-DFLASH_PREFILL_NROW_DOWN_M4_2ROW \
	-DFLASH_PREFILL_NROW_GATEUP_M4_16ROW \
	-DFLASH_PREFILL_NROW_EXPERT_PHASE_TIMING

n128gateup16row: $(INFER_SRC) $(INFER_DEPS)
	$(CC) $(N128_GATEUP16ROW_CFLAGS) $(FRAMEWORKS) $(LDFLAGS) $(INFER_SRC) -o "$(N128_GATEUP16ROW_TARGET)"
	@echo "Built benchmark-only $(N128_GATEUP16ROW_TARGET); production ./$(INFER_TARGET) and prior N128 candidates were not replaced."

# Serving-path promotion candidate for the validated N128 geometry. This uses
# the normal production N-row path but writes a separate binary; ./infer remains the N128 production build.
N128_SERVE8ROW_TARGET = ../Testing/Temporary Testing Files/Apps/infer-n128-m4-8row-serving-candidate
N128_SERVE8ROW_CFLAGS = $(CFLAGS) \
	-DFLASH_PREFILL_NROW_PRODUCTION \
	-DFLASH_PREFILL_NROW_ASYNC \
	-DFLASH_PREFILL_NROW_N128 \
	-DFLASH_PREFILL_NROW_DOWN_M4_2ROW \
	-DFLASH_PREFILL_NROW_GATEUP_M4_8ROW

n128serve8row: $(INFER_SRC) $(INFER_DEPS)
	$(CC) $(N128_SERVE8ROW_CFLAGS) $(FRAMEWORKS) $(LDFLAGS) $(INFER_SRC) -o "$(N128_SERVE8ROW_TARGET)"
	@echo "Built serving candidate $(N128_SERVE8ROW_TARGET); production ./$(INFER_TARGET) was not replaced."

# Retained production-style N128 serving target for the fixed-bit gate+up
# specialization. Bitsplit is now the production default; this separate binary remains useful for isolated A/B/regression testing.
N128_SERVE8BITS_TARGET = ../Testing/Temporary Testing Files/Apps/infer-n128-m4-8row-bitsplit-serving-candidate
N128_SERVE8BITS_CFLAGS = $(CFLAGS) \
	-DFLASH_PREFILL_NROW_PRODUCTION \
	-DFLASH_PREFILL_NROW_ASYNC \
	-DFLASH_PREFILL_NROW_N128 \
	-DFLASH_PREFILL_NROW_DOWN_M4_2ROW \
	-DFLASH_PREFILL_NROW_GATEUP_M4_8ROW_BITSPLIT

n128serve8bits: $(INFER_SRC) $(INFER_DEPS)
	$(CC) $(N128_SERVE8BITS_CFLAGS) $(FRAMEWORKS) $(LDFLAGS) $(INFER_SRC) -o "$(N128_SERVE8BITS_TARGET)"
	@echo "Built serving candidate $(N128_SERVE8BITS_TARGET); production ./$(INFER_TARGET) was not replaced."

# Build the chat client (thin HTTP/SSE client + linenoise line editor)
$(CHAT_TARGET): $(CHAT_SRC) linenoise.c linenoise.h
	$(CC) -O2 -Wall -fobjc-arc -framework Foundation $(CHAT_SRC) linenoise.c -o $(CHAT_TARGET)

clean:
	rm -f $(TARGET) $(INFER_TARGET) "$(N128_BENCH_TARGET)" "$(N128_GATEUP8_TARGET)" "$(N128_GATEUP4ROW_TARGET)" "$(N128_GATEUP8ROW_TARGET)" "$(N128_GATEUP8CACHE_TARGET)" "$(N128_GATEUP8BITS_TARGET)" "$(N128_DOWNBITS_TARGET)" "$(N128_GATEUP16ROW_TARGET)" "$(N128_SERVE8ROW_TARGET)" "$(N128_SERVE8BITS_TARGET)" $(CHAT_TARGET) $(SHADER_AIR) $(SHADER_LIB)

# Run targets
run: $(TARGET)
	./$(TARGET) --layer 0 --expert 0

verify: $(TARGET)
	./$(TARGET) --layer 0 --expert 0 --verify

fast: $(TARGET)
	./$(TARGET) --layer 0 --expert 0 --fast --verify

bench: $(TARGET)
	./$(TARGET) --layer 0 --expert 0 --fast --benchmark

moe: $(TARGET)
	./$(TARGET) --layer 0 --fast --moe

moebench: $(TARGET)
	./$(TARGET) --layer 0 --fast --moe --benchmark

full: $(TARGET)
	./$(TARGET) --fast --full --k 4

fullbench: $(TARGET)
	./$(TARGET) --fast --full --k 4 --benchmark

# Inference engine targets
build-infer: $(INFER_TARGET)

infer-run: $(INFER_TARGET)
	./$(INFER_TARGET) --prompt "Hello, what is" --tokens 20 --k 4

# Chat TUI targets (use: make chat)

chat-run: $(CHAT_TARGET)
	./$(CHAT_TARGET) --k 4
