# Flash-iOS LM Studio document generator — experimental 0.1.0

This integration intercepts text attachments through LM Studio's documented plugin SDK message APIs and includes their parsed content in the user turn forwarded to Flash-iOS's OpenAI-compatible Chat Completions API.

## Mac installation (after verifying against installed SDK)
```sh
cd '/Users/knagel/My Drive/Flash-iOS/LMStudioGenerator'
npm install
npm run build
lms dev
```

Generator: flash-ios/openai-compat-documents. Set model qwen3.5; Base URL http://127.0.0.1:11242/v1 to capture the outbound JSON or http://127.0.0.1:11241/v1 for production Flash-iOS. Existing generators remain untouched.

Inputs: txt, log, md, json, csv, tsv, yaml, xml, ini, conf. Non-image files are parsed with ctl.client.files.parseDocument, consumed and converted to filename-delimited text within their original user turn. On parse failure the preprocessor rejects rather than silently omitting text. Repeated turn handling keeps the text in history without re-injecting consumed file handles.

Context: No tokenizer qualified yet. A conservative serialized-character rejection threshold is a safety cap, NOT verified token accounting. Large input is rejected, never silently truncated.

## Validation status
NOT QUALIFIED. Source created for review; this session did not complete npm installation/typecheck, LM Studio GUI registration, 11242 capture, or Flash-iOS 11241 live run.

SDK examples: https://lmstudio.ai/ceveyne/gemini-compat-endpoint/files/src/preprocessor.ts and https://lmstudio.ai/killerrr777/rag-v2/files/src/promptPreprocessor.ts.
