import express from "express";
import type { Database } from "better-sqlite3";
import { requireLogin } from "../middlewares/auth";

export function createAdminRouter({ db }: { db: Database }): express.Router {
  const router = express.Router();

  router.get("/me", requireLogin, (req, res) => {
    res.json({ ok: true, user: req.session.user });
  });

  // demo: reset db chunks/chats only (keep users)
  router.post("/admin/reset", requireLogin, (req, res) => {
    db.prepare("DELETE FROM chunks").run();
    db.prepare("DELETE FROM chats").run();
    res.json({ ok: true, message: "chunks/chats cleared (users preserved)" });
  });

  return router;
}
