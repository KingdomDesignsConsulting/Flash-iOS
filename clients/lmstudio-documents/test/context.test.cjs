const test = require('node:test');
const assert = require('node:assert/strict');
const {generate} = require('../dist/generator.js');

test('oversized UTF-8 document is rejected before contacting the endpoint', async () => {
  const text = '🛠'.repeat(9000);
  const ctl = {
    getPluginConfig: () => ({get: key => ({maxOutputTokens: 2048, model: 'qwen3.5', debug: false})[key]}),
    getGlobalPluginConfig: () => ({get: key => ({baseUrl: 'http://127.0.0.1:1/v1', apiKey: ''})[key]}),
    getToolDefinitions: () => [],
    onAborted: () => {},
  };
  const chat = [{getRole: () => 'user', getText: () => text}];
  await assert.rejects(generate(ctl, chat), /Context safety cap exceeded/);
});
