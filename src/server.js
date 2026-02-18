const path = require("path");
const express = require("express");
const session = require("express-session");
const cookieParser = require("cookie-parser");
const morgan = require("morgan");
require("dotenv").config();

const { initDb } = require("./services/db");
const { attachRoles } = require("./middlewares/rbac");
const { createAuthRouter } = require("./routes/auth.route");
const { createChatRouter } = require("./routes/chat.route");
const { createIngestRouter } = require("./routes/ingest.route");
const { createLibraryRouter } = require("./routes/library.route");
const { createHealthRouter } = require("./routes/health.route");
const { createAuditRouter } = require("./routes/audit.route");
const { createAdminRouter } = require("./routes/admin.route");

const PORT = Number(process.env.PORT || 8000);
const SQLITE_PATH = process.env.SQLITE_PATH || "./data/app.db";
const SESSION_SECRET = process.env.SESSION_SECRET || "change-me";

// If you are behind a reverse proxy (nginx/traefik), set TRUST_PROXY=1
const app = express();
app.disable("x-powered-by");
if (process.env.TRUST_PROXY === "1") {
  console.log("[server] trust proxy enabled");
  app.set("trust proxy", 1);
}

app.use(morgan("dev"));
app.use(express.json({ limit: "2mb" }));
app.use(cookieParser());

const db = initDb(SQLITE_PATH);

// ✅ IMPORTANT: session middleware must run BEFORE any middleware that reads req.session
app.use(
  session({
    name: "lawrag.sid",
    secret: SESSION_SECRET,
    resave: false,
    saveUninitialized: false,
    cookie: {
      httpOnly: true,
      // If FE and API are on different origins (e.g. 3000 vs 8000), you need:
      // sameSite: "none" + secure: true (HTTPS). For same-origin demo, "lax" is fine.
      sameSite: process.env.COOKIE_SAMESITE || "lax",
      secure: process.env.COOKIE_SECURE === "true" || false,
      maxAge: 1000 * 60 * 60 * 24 * 7,
    },
  })
);

// attach roles to session.user (after session)
app.use(attachRoles(db));

// Routes
app.use("/api/health", createHealthRouter());
app.use("/api/auth", createAuthRouter({ db }));
app.use("/api", createAdminRouter({ db }));
app.use("/api", createIngestRouter({ db }));
app.use("/api", createLibraryRouter({ db }));
app.use("/api", createChatRouter({ db }));
app.use("/api", createAuditRouter({ db }));

// Static
app.use(express.static(path.join(__dirname, "..", "public")));

app.use((req, res) => res.status(404).json({ error: "not found" }));

app.listen(PORT, () => {
  console.log(`\n[law-rag-agent] server listening on http://localhost:${PORT}`);
});
