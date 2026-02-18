const express = require("express");
const { requireLogin } = require("../middlewares/auth");
const { createOllama } = require("../lib/ollama");
const { answerWithRag } = require("../services/agent.service");
const { audit } = require("../services/audit.service");

function createChatRouter({ db }) {
  const router = express.Router();

  const ollama = createOllama({ baseUrl: process.env.OLLAMA_BASE_URL || "http://127.0.0.1:11434" });
  const llmModel = process.env.LLM_MODEL || "llama3.1";
  const embedModel = process.env.EMBED_MODEL || "nomic-embed-text";
  const topK = Number(process.env.TOP_K || 6);

  router.post("/chat", requireLogin, async (req, res) => {
    try {
      const question = String(req.body?.question || "").trim();
      if (!question) return res.status(400).json({ error: "question is required" });

      const roles = req.session.user.roles || ["user"];

      audit(db, {
        userId: req.session.user.id,
        clientId: req.session.user.clientId,
        eventType: "chat_request",
        payload: { question, roles },
      });

      const { answer, citations } = await answerWithRag({
        db,
        ollama,
        llmModel,
        embedModel,
        question,
        topK,
        userRoles: roles,
        auditCtx: { userId: req.session.user.id, clientId: req.session.user.clientId },
      });

      db.prepare(
        "INSERT INTO chats (user_id, client_id, question, answer, citations_json, created_at) VALUES (?, ?, ?, ?, ?, ?)"
      ).run(
        req.session.user.id,
        req.session.user.clientId,
        question,
        answer,
        JSON.stringify(citations),
        new Date().toISOString()
      );

      audit(db, {
        userId: req.session.user.id,
        clientId: req.session.user.clientId,
        eventType: "chat_response",
        payload: { citationsCount: citations.length },
      });

      res.json({ ok: true, answer });
    } catch (e) {
      res.status(500).json({ error: e.message || "chat error" });
    }
  });

  return router;
}

module.exports = { createChatRouter };
