import type {PluginContext} from "@lmstudio/sdk";
import {configSchematics,globalConfigSchematics} from "./config";
import {injectDocuments} from "./documents";
import {generate} from "./generator";
export async function main(context:PluginContext){context.withConfigSchematics(configSchematics);context.withGlobalConfigSchematics(globalConfigSchematics);context.withPromptPreprocessor(injectDocuments);context.withGenerator(generate);}