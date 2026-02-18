const axios = require("axios");

/**
 * Ollama client with configurable timeouts.
 * - Default timeout is 300s to survive cold-start model loading on CPU.
 * - You can override via env:
 *   - OLLAMA_TIMEOUT_MS (global)
 *   - OLLAMA_CHAT_TIMEOUT_MS
 *   - OLLAMA_EMBED_TIMEOUT_MS
 */
function createOllama({ baseUrl, timeoutMs, chatTimeoutMs, embedTimeoutMs } = {}) {
  const globalTimeout =
    Number(timeoutMs || process.env.OLLAMA_TIMEOUT_MS || 300000) || 300000;

  const chatTimeout =
    Number(chatTimeoutMs || process.env.OLLAMA_CHAT_TIMEOUT_MS || globalTimeout) ||
    globalTimeout;

  const embedTimeout =
    Number(embedTimeoutMs || process.env.OLLAMA_EMBED_TIMEOUT_MS || globalTimeout) ||
    globalTimeout;

  const http = axios.create({ baseURL: baseUrl, timeout: globalTimeout });

  async function chat({ model, messages, options = {} }) {
    const { data } = await http.post(
      "/api/chat",
      { model, messages, stream: false, options },
      { timeout: chatTimeout }
    );
    return data?.message?.content || "";
  }

  async function embed({ model, input }) {
    const { data } = await http.post(
      "/api/embeddings",
      { model, prompt: input },
      { timeout: embedTimeout }
    );
    if (!data?.embedding) throw new Error("embedding failed");
    return data.embedding;
  }

  return { chat, embed };
}

module.exports = { createOllama };
