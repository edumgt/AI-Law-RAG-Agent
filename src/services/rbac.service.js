function getUserRoles(db, userId) {
  const rows = db.prepare("SELECT role_name FROM user_roles WHERE user_id = ?").all(userId);
  return rows.map(r => r.role_name);
}

function ensureUserRole(db, userId, roleName) {
  db.prepare(
    "INSERT OR IGNORE INTO user_roles (user_id, role_name, created_at) VALUES (?, ?, ?)"
  ).run(userId, roleName, new Date().toISOString());
}

function isAdmin(roles) {
  return roles.includes("admin");
}

module.exports = { getUserRoles, ensureUserRole, isAdmin };
