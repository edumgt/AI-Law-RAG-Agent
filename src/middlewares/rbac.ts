import type { Request, Response, NextFunction } from "express";
import type { Database } from "better-sqlite3";
import { getUserRoles } from "../services/rbac.service";

export function attachRoles(db: Database) {
  return (req: Request, res: Response, next: NextFunction): void => {
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

export function requireAdmin(req: Request, res: Response, next: NextFunction): void {
  const roles = req.session?.user?.roles || [];
  if (!roles.includes("admin")) {
    res.status(403).json({ error: "admin required" });
    return;
  }
  next();
}
