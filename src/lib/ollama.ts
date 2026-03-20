import axios, { AxiosInstance } from "axios";

export interface OllamaOptions {
  baseUrl?: string;
  timeoutMs?: number;
  chatTimeoutMs?: number;
  embedTimeoutMs?: number;
}

export interface OllamaMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface OllamaChatOptions {
  model: string;
  messages: OllamaMessage[];
  options?: Record<string, unknown>;
}

export interface OllamaEmbedOptions {
  model: string;
  input: string;
}

export interface OllamaClient {
  chat(opts: OllamaChatOptions): Promise<string>;
  embed(opts: OllamaEmbedOptions): Promise<number[]>;
}

/**
 * Ollama client with configurable timeouts.
 * - Default timeout is 300s to survive cold-start model loading on CPU.
 * - You can override via env:
 *   - OLLAMA_TIMEOUT_MS (global)
 *   - OLLAMA_CHAT_TIMEOUT_MS
 *   - OLLAMA_EMBED_TIMEOUT_MS
 */
export function createOllama({
  baseUrl,
  timeoutMs,
  chatTimeoutMs,
  embedTimeoutMs,
}: OllamaOptions = {}): OllamaClient {
  const globalTimeout =
    Number(timeoutMs || process.env.OLLAMA_TIMEOUT_MS || 300000) || 300000;

  const chatTimeout =
    Number(chatTimeoutMs || process.env.OLLAMA_CHAT_TIMEOUT_MS || globalTimeout) ||
    globalTimeout;

  const embedTimeout =
    Number(embedTimeoutMs || process.env.OLLAMA_EMBED_TIMEOUT_MS || globalTimeout) ||
    globalTimeout;

  const http: AxiosInstance = axios.create({ baseURL: baseUrl, timeout: globalTimeout });

  async function chat({ model, messages, options = {} }: OllamaChatOptions): Promise<string> {
    const { data } = await http.post(
      "/api/chat",
      { model, messages, stream: false, options },
      { timeout: chatTimeout }
    );
    return (data?.message?.content as string) || "";
  }

  async function embed({ model, input }: OllamaEmbedOptions): Promise<number[]> {
    const { data } = await http.post(
      "/api/embeddings",
      { model, prompt: input },
      { timeout: embedTimeout }
    );
    if (!data?.embedding) throw new Error("embedding failed");
    return data.embedding as number[];
  }

  return { chat, embed };
}
