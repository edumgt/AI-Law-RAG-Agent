import express from "express";

export function createHealthRouter(): express.Router {
  const router = express.Router();
  router.get("/", (req, res) => res.json({ ok: true, ts: new Date().toISOString() }));
  return router;
}
