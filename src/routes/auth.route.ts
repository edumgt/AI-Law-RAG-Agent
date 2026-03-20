import express from "express";
import bcrypt from "bcryptjs";
import { randomBytes } from "crypto";
import type { Database } from "better-sqlite3";
import { ensureUserRole } from "../services/rbac.service";

interface UserRow {
  id: number;
  name: string;
  email: string;
  password_hash: string;
  client_id: string;
}

interface ExistsRow {
  id: number;
}

interface InsertResult {
  lastInsertRowid: number | bigint;
}

function normalizeEmail(email: string): string {
  return String(email || "")
    .trim()
    .toLowerCase();
}

function isAdminEmail(email: string): boolean {
  const list = String(process.env.ADMIN_EMAILS || "")
    .split(",")
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean);
  return list.includes(String(email || "").toLowerCase());
}

function generateClientId(): string {
  return "C_" + randomBytes(9).toString("base64url");
}

export function createAuthRouter({ db }: { db: Database }): express.Router {
  const router = express.Router();

  router.post("/register", (req, res) => {
    const name = String(req.body?.name || "").trim();
    const email = normalizeEmail(req.body?.email);
    const password = String(req.body?.password || "");

    if (!name || !email || password.length < 4) {
      return res.status(400).json({ error: "invalid input" });
    }

    const exists = db.prepare("SELECT id FROM users WHERE email = ?").get(email) as ExistsRow | undefined;
    if (exists) return res.status(409).json({ error: "email already exists" });

    const passwordHash = bcrypt.hashSync(password, 10);
    const clientId = generateClientId();
    const createdAt = new Date().toISOString();

    const info = db
      .prepare(
        "INSERT INTO users (name, email, password_hash, client_id, created_at, primary_role) VALUES (?, ?, ?, ?, ?, ?)"
      )
      .run(name, email, passwordHash, clientId, createdAt, "user") as InsertResult;

    const userId = info.lastInsertRowid;

    // default role
    ensureUserRole(db, userId, "user");

    // optional admin seeding
    if (isAdminEmail(email)) {
      ensureUserRole(db, userId, "admin");
      db.prepare("UPDATE users SET primary_role = ? WHERE id = ?").run("admin", userId);
    }

    res.json({ ok: true, clientId });
  });

  router.post("/login", (req, res) => {
    const email = normalizeEmail(req.body?.email);
    const password = String(req.body?.password || "");

    const user = db
      .prepare("SELECT id, name, email, password_hash, client_id FROM users WHERE email = ?")
      .get(email) as UserRow | undefined;
    if (!user) return res.status(401).json({ error: "invalid credentials" });

    const ok = bcrypt.compareSync(password, user.password_hash);
    if (!ok) return res.status(401).json({ error: "invalid credentials" });

    // session 유지: userId + clientId (+roles in middleware)
    req.session.user = {
      id: user.id,
      name: user.name,
      email: user.email,
      clientId: user.client_id,
      roles: [], // will be attached by middleware
    };
    res.json({ ok: true, user: req.session.user });
  });

  router.post("/logout", (req, res) => {
    req.session.destroy(() => {
      res.clearCookie("lawrag.sid");
      res.json({ ok: true });
    });
  });

  return router;
}
