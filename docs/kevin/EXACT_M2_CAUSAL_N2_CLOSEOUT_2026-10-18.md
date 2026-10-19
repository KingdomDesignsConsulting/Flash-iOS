# Exact-M2 causal N=2 research closeout (2026-10-18)

**Decision: keep validated serial exact-M2 and raw checkpoints as the supported path. Do not promote causal N=2, Stage A/B1, or Stage B2.** This is a documentation decision, not a runtime or checkpoint format change.

## Experiments and conclusions

- Exact-M2 state/geometry repair passed the established 30/30 raw/zero4k oracle matrix. The raw two-bank GPU state is approximately 191.27 MiB. Keep raw as default; zero4k was experimental and could increase peak physical footprint.
- Captured component N=2 routed Q2/Q4 projection replay was bit-exact and approximately 9.22% faster at the isolated component level, but this was not a full causal or end-to-end speedup. N=4 was slower in the component test.
- Live causal N=2 layer-major execution proved feasible, including genuine shared-expert count=2 groups (192/168/147 for accept0/1/2), exact layer-by-layer hidden/state/KV, commit/rollback and continuation on the tested raw/32 fixtures. Whole-round performance regressed versus serial.
- Stage A reused the native eight-worker expert I/O pool, cutting accept2 union staging from 81.47 to 37.42 ms and complete causal round from 232.67 to 191.59 ms, still versus 115.55 ms serial in that run. Retain as an isolated research artifact.
- Stage B1 safely removed 40 host waits per pair (200 to 160), leaving 280 command buffers. Causal state remained exact, but paired latency did not demonstrate a repeatable speedup; do not promote.
- The final host/GPU attribution diagnostic found 22/40 B1 matched wins; pooled paired median C−B was −2.359 ms with large variability. The exposed grouped→first shared gap was only ~0.08–0.18 ms. Even the optimistic ~10–12 ms broader consolidation-gap ceiling leaves the causal prototype slower than contemporaneous serial. **NO-GO for Stage B2 as a serial-beating strategy.**

## Interpretation and future work

The current causal architecture's expense is not explained by one missing GPU barrier. The diagnostic also observed serial timing drift in GPU execution intervals, not just host submission gaps. Frequency/thermal and SSD I/O causation was **not established**. Follow-up, if explicitly commissioned, should first stabilize observer/system conditions and assess the serial verifier's native mmap/pread path, activation/bank allocation, and CPU handoff slack. Do not restart speculative kernel N=4 or command-buffer consolidation without a new evidence-based gate.

## Preservation and source authority

The completed Work reports say production `infer`, port 11436, live caches/checkpoints, checkpoint format, and raw default were untouched; no experimental commits/pushes occurred. Their experiments used an authoritative Google Drive source snapshot that diverged from this Git repository. **Do not overwrite Drive-validated engine files with GitHub contents or claim GitHub commits synchronize the Drive mirror.** The present commit only adds this research closeout note and does not contain experimental patches.

Drive evidence:
- [Causal scheduler feasibility report](https://drive.google.com/file/d/1DKG_EAjSzJPrGhu8XU0c8IjuhfoBexpg/view)
- [Stage A results](https://drive.google.com/file/d/1hIlgFnJ-vTUPtC7JjiBZgpi4BsH-Vc-j/view)
- [Stage B1 results](https://drive.google.com/file/d/1T8Zo-cuYXpbocyq4kBHs3jmHRpVP7_he/view)
- [Host/GPU critical-path report](https://drive.google.com/file/d/1Nq3Ti9tQFuhlMLYGxzOutkM0LcTj5Hsl/view)
- [Host/GPU traces and evidence](https://drive.google.com/file/d/1lt9fHJpF52-wO0jTKnBlrlGkrJNeIAa0/view)

No broader causal-N2 production qualification or long-context claim is made by these fixture tests.
