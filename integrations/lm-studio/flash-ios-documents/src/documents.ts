import type { ChatMessage, PromptPreprocessorController } from "@lmstudio/sdk";
const START = "<flash-ios-document";
const END = "</flash-ios-document>";
const MAX_CHARS = 1000000;
export async function injectDocuments(ctl: PromptPreprocessorController, message: ChatMessage) {
  const files = message.getFiles(ctl.client).filter(f => f.type !== "image");
  if (!files.length) return message;
  const parsed: Array<{name:string;content:string}> = [];
  for (const file of files) {
    if (ctl.abortSignal.aborted) throw new Error("Attachment parsing cancelled");
    const name = file.name || "unnamed-document";
    if (!/\.(txt|log|md|json|csv|tsv|yaml|yml|xml|ini|conf|cfg)$/i.test(name)) throw new Error(`Unsupported attachment: ${name}`);
    const {content} = await ctl.client.files.parseDocument(file,{signal:ctl.abortSignal});
    if (typeof content !== "string" || !content.length) throw new Error(`Empty or unreadable attachment: ${name}`);
    if (content.length > MAX_CHARS) throw new Error(`Attachment ${name} exceeds ${MAX_CHARS} characters; split it before sending.`);
    parsed.push({name,content});
  }
  const content = message.getText();
  if (content.includes(START)) throw new Error("Document marker already present; refusing to inject twice");
  const combined = [content, ...parsed.map(d => `${START} name=${JSON.stringify(d.name)}>\n${d.content}\n${END}`)].join("\n\n");
  message.consumeFiles(ctl.client, f => f.type !== "image");
  message.replaceText(combined);
  return message;
}