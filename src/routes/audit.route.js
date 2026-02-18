const express = require("express");
const { requireLogin } = require("../middlewares/auth");
const { requireAdmin } = require("../middlewares/rbac");
const { recentAudits } = require("../services/audit.service");

function createAuditRouter({ db }) {
  const router = express.Router();

  router.get("/audit/recent", requireLogin, requireAdmin, (req, res) => {
    const limit = Math.min(Number(req.query?.limit || 50), 200);
    const items = recentAudits(db, limit);
    res.json({ ok: true, items });
  });

  return router;
}

module.exports = { createAuditRouter };
