# Flash-iOS document generator for LM Studio

This LM Studio plugin sends attached documents with the user message to Flash-iOS's OpenAI-compatible chat endpoint. It uses the LM Studio prompt preprocessor to parse each non-image attachment, inserts the filename and extracted text in the message, and consumes the file handle so history does not inject it twice.

## Install

From this directory, with Node.js 22 and LM Studio installed:

```sh
npm ci
npm run build
npm test
lms dev --install --yes
```

Select `flash-ios/openai-compat-documents` in LM Studio. Set the model ID to `qwen3.5` and the Base URL to `http://127.0.0.1:11241/v1`. To inspect outbound JSON, run `node test/capture-server.cjs` and temporarily use `http://127.0.0.1:11242/v1`.

The plugin was built against LM Studio SDK 1.4.0. It uses the SDK document parser for text, PDF, and Word attachments. Parser failures and empty or overlong extracted text produce visible errors; the attachment is not consumed on those failures. Images stay attached for other LM Studio handling and are not forwarded by this plugin.

## Context and cancellation

The generator assumes Flash-iOS's qualified 32K context. It reserves the configured output tokens plus 2,048 tokens for chat framing and rejects a request if serialized messages and tool definitions exceed the remaining budget **in UTF-8 bytes**. This deliberately overestimates prompt tokens. It does not silently truncate a document. This is a safety bound, not exact Qwen token accounting.

LM Studio's cancel action aborts the upstream HTTP stream. The HTTP request timeout is ten minutes to allow long local prefill.

## Verified on the user's Mac

- `npm run build` and `npm test` pass with the installed SDK 1.4.0 and OpenAI client 5.23.2.
- LM Studio loaded the plugin and sent `crash-oct1-1854-cutoff.txt` to the capture server with its filename and all 9,789 source characters in the user message.
- A follow-up turn preserved one copy of the attachment in history.
- Capture-server streaming produced a visible LM Studio response.

The live Flash-iOS result and UI cancellation test are recorded separately in the validation report included with the release package.
