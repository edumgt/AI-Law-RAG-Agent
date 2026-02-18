const express = require("express");
const bcrypt = require("bcryptjs");
const { nanoid } = require("nanoid");
const { ensureUserRole } = require("../services/rbac.service");

function normalizeEmail(email) {
  return String(email || "").trim().toLowerCase();
}

function isAdminEmail(email) {
  const list = String(process.env.ADMIN_EMAILS || "").split(",").map(s => s.trim().toLowerCase()).filter(Boolean);
  return list.includes(String(email || "").toLowerCase());
}

function createAuthRouter({ db }) {
  const router = express.Router();

  router.post("/register", (req, res) => {
    const name = String(req.body?.name || "").trim();
    const email = normalizeEmail(req.body?.email);
    const password = String(req.body?.password || "");

    if (!name || !email || password.length < 4) {
      return res.status(400).json({ error: "invalid input" });
    }

    const exists = db.prepare("SELECT id FROM users WHERE email = ?").get(email);
    if (exists) return res.status(409).json({ error: "email already exists" });

    const passwordHash = bcrypt.hashSync(password, 10);
    const clientId = "C_" + nanoid(12);
    const createdAt = new Date().toISOString();

    const info = db.prepare(
      "INSERT INTO users (name, email, password_hash, client_id, created_at, primary_role) VALUES (?, ?, ?, ?, ?, ?)"
    ).run(name, email, passwordHash, clientId, createdAt, "user");

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

    const user = db.prepare("SELECT id, name, email, password_hash, client_id FROM users WHERE email = ?").get(email);
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

module.exports = { createAuthRouter };
