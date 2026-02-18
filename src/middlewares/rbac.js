const { getUserRoles } = require("../services/rbac.service");

function attachRoles(db) {
  return (req, res, next) => {
    if (!req.session?.user?.id) return next();
    try {
      const roles = getUserRoles(db, req.session.user.id);
      req.session.user.roles = roles;
      next();
    } catch (e) {
      next(e);
    }
  };
}

function requireAdmin(req, res, next) {
  const roles = req.session?.user?.roles || [];
  if (!roles.includes("admin")) return res.status(403).json({ error: "admin required" });
  next();
}

module.exports = { attachRoles, requireAdmin };
