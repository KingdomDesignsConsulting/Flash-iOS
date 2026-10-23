const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

test('LM Studio cancellation aborts the upstream streaming request', async () => {
  let requestStarted;
  const started = new Promise(resolve => {requestStarted = resolve});
  let upstreamSignal;
  class FakeOpenAI {
    constructor() {
      this.chat = {completions: {create: async (_body, options) => {
        upstreamSignal = options.signal;
        requestStarted();
        return {async *[Symbol.asyncIterator]() {
          yield {choices: [{delta: {content: 'first fragment'}}]};
          await new Promise((_, reject) => options.signal.addEventListener('abort', () => reject(new Error('aborted')), {once: true}));
        }};
      }}};
    }
  }
  const code = fs.readFileSync(require.resolve('../dist/generator.js'), 'utf8');
  const moduleObj = {exports: {}};
  vm.runInNewContext(code, {
    module: moduleObj, exports: moduleObj.exports, Buffer, console, AbortController,
    require: name => name === 'openai' ? {__esModule: true, default: FakeOpenAI} : name === './config' ? {} : require(name),
  });
  let abort;
  const fragments = [];
  const ctl = {
    getPluginConfig: () => ({get: key => ({maxOutputTokens: 256, model: 'qwen3.5', debug: false, temperature: 0.7})[key]}),
    getGlobalPluginConfig: () => ({get: key => ({baseUrl: 'http://127.0.0.1:11242/v1', apiKey: ''})[key]}),
    getToolDefinitions: () => [],
    onAborted: callback => {abort = callback},
    fragmentGenerated: text => fragments.push(text),
  };
  const chat = [{getRole: () => 'user', getText: () => 'hello'}];
  const running = moduleObj.exports.generate(ctl, chat);
  await started;
  await new Promise(resolve => setImmediate(resolve));
  abort();
  await running;
  assert.equal(upstreamSignal.aborted, true);
  assert.deepEqual(fragments, ['first fragment']);
});
