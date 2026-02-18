const express = require("express");

function createHealthRouter() {
  const router = express.Router();
  router.get("/", (req, res) => res.json({ ok: true, ts: new Date().toISOString() }));
  return router;
}

module.exports = { createHealthRouter };
