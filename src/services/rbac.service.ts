import type { Database } from "better-sqlite3";

export function getUserRoles(db: Database, userId: number): string[] {
  const rows = db
    .prepare("SELECT role_name FROM user_roles WHERE user_id = ?")
    .all(userId) as Array<{ role_name: string }>;
  return rows.map((r) => r.role_name);
}

export function ensureUserRole(db: Database, userId: number | bigint, roleName: string): void {
  db.prepare(
    "INSERT OR IGNORE INTO user_roles (user_id, role_name, created_at) VALUES (?, ?, ?)"
  ).run(userId, roleName, new Date().toISOString());
}

export function isAdmin(roles: string[]): boolean {
  return roles.includes("admin");
}
