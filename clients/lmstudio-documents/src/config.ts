import { createConfigSchematics } from "@lmstudio/sdk";
export const globalConfigSchematics = createConfigSchematics()
 .field("baseUrl","string",{displayName:"Base URL"},"http://127.0.0.1:11243/v1")
 .field("totalDeadlineSeconds","numeric",{displayName:"Total request deadline (seconds)",min:1,max:86400},600)
 .field("idleDeadlineSeconds","numeric",{displayName:"Stream idle deadline (seconds)",min:1,max:86400},120)
 .field("apiKey","string",{displayName:"API key (optional)",isProtected:true},"").build();
export const configSchematics = createConfigSchematics()
 .field("model","string",{displayName:"Model ID"},"qwen3.5")
 .field("debug","boolean",{displayName:"Debug request metadata"},false)
 .field("temperature","numeric",{displayName:"Temperature",min:0,max:2},0.7)
 .field("maxOutputTokens","numeric",{displayName:"Reserved output tokens",min:256,max:8192},2048).build();
