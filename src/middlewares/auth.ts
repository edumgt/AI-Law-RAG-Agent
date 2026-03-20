import type { Request, Response, NextFunction } from "express";

export function requireLogin(req: Request, res: Response, next: NextFunction): void {
  if (!req.session || !req.session.user) {
    res.status(401).json({ error: "login required" });
    return;
  }
  next();
}
