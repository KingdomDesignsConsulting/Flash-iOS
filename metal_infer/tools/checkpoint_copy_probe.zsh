#!/bin/zsh
# Instrumentation-only exact-M2 short oracle repeatability probe.
set -euo pipefail
cd "${0:A:h:h}"
[[ -f tools/exact_m2_zero4k_manual.zsh ]] || { print -u2 'Missing exact-M2 helper'; exit 2; }
N="${1:-3}"
[[ "$N" == <-> && "$N" -ge 1 && "$N" -le 20 ]] || { print -u2 'Usage: checkpoint_copy_probe.zsh [repeats 1..20]'; exit 2; }
OUT="benchmark-logs/checkpoint-copy-probe-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
for codec in raw zero4k; do
  for ((i=1;i<=N;i++)); do
    log="$OUT/$codec-32-accept0-run$i.log"
    print "$codec run $i: $log"
    if [[ "$codec" == zero4k ]]; then
      FLASH_TARGET_GPU_ZERO4K=1 /usr/bin/time -l zsh tools/exact_m2_zero4k_manual.zsh oracle 32 accept0 > "$log" 2>&1 || { print -u2 "FAIL $log"; exit 1; }
    else
      FLASH_TARGET_GPU_ZERO4K=0 /usr/bin/time -l zsh tools/exact_m2_zero4k_manual.zsh oracle 32 accept0 > "$log" 2>&1 || { print -u2 "FAIL $log"; exit 1; }
    fi
    grep -q 'RESULT=PASS' "$log" || { print -u2 "Missing PASS: $log"; exit 1; }
  done
done
print "Completed: $OUT"
print 'NOTE: verify helper forwards FLASH_TARGET_GPU_ZERO4K and inspect underlying infer subprocess logs for peak footprint.'
