import express from "express";
import type { Database } from "better-sqlite3";
import { requireLogin } from "../middlewares/auth";
import { requireAdmin } from "../middlewares/rbac";
import { recentAudits } from "../services/audit.service";

export function createAuditRouter({ db }: { db: Database }): express.Router {
  const router = express.Router();

  router.get("/audit/recent", requireLogin, requireAdmin, (req, res) => {
    const limit = Math.min(Number(req.query?.limit || 50), 200);
    const items = recentAudits(db, limit);
    res.json({ ok: true, items });
  });

  return router;
}
