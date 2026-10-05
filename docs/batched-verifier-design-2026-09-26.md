# Minimal multi-position verifier design

The current target executes one position at a time. Full attention has causal prefix KV, and 30 of 40 layers contain a mutable DeltaNet and depthwise convolution state. Their current kernels update that state for one token. MoE routing also occurs inside each token's layer pipeline, before later-layer hidden states are known. Reordering the whole model by layer would require new multi-position kernels and expert grouping across all 40 layers.

The first executable prototype will therefore **batch only the final LM-head projection**. It will:

1. Restore a disposable captured prefix state.
2. Advance the N known candidate tokens through the existing transformer layer path in causal order, collecting the N hidden states whose logits verify each candidate.
3. Apply final RMS normalization to each collected hidden state.
4. Project all N normalized states with one benchmark-only Metal kernel. Each output row reuses the same quantized LM-head weights for all N positions.
5. Compare each position's argmax/logits and the final KV, DeltaNet, and convolution state against the serial control.

This is a **partially batched verifier**, not a full block transformer. Full attention, DeltaNet, convolution, dense layer projections, MoE routing and expert execution remain serial. The batch operation can measure the LM-head savings and establish a correctness/test harness for later work, but it cannot by itself test expert grouping or eliminate N-fold expert traffic. State restore/copy remains outside timed verification, matching the serial benchmark.

The experiment uses the same 1/2/4/8 candidate sequence and production model execution flags as the serial benchmark. No checkpoint, warm-profile, resident-session, API, or production decode path changes are needed.
