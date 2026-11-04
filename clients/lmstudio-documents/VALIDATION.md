# Version 0.2.0 qualification (2026-10-25)

- TypeScript build: PASS with SDK 1.4.0 / Node 22.19.0.
- npm test: 19/19 PASS against deterministic HTTP servers and actual SDK Chat objects.
- `node test/live-sdk-documents.cjs --out ../../benchmark-logs/live-sdk-documents.json`:
  PASS on real LM Studio 0.4.26 build 4 document preparation/parsing. Exactly one
  synthetic UTF-8 attachment copy was forwarded in each of two full histories.
  Prediction controller was a mock/capture endpoint, not the GUI.
- Live GUI installation/cancellation/regeneration for this release: NOT TESTED.
- SDK entry point: safe stateless forwarding. Scoped resident adapter is tested
  independently and remains disabled without a verified identity contract.
- Version 0.1.1 historical UI success does not qualify 0.2.0 UI behavior.

See repository docs/session-continuity-engineering-2026-10-25.md and the JSON
results for exact coverage and release blockers. Keep production rollout blocked.
