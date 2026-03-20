import fs from "fs";
import path from "path";

export function ensureDir(p: string): void {
  fs.mkdirSync(p, { recursive: true });
}

export function writeJson(fp: string, obj: unknown): void {
  ensureDir(path.dirname(fp));
  fs.writeFileSync(fp, JSON.stringify(obj, null, 2), "utf-8");
}

export function appendJsonl(fp: string, obj: unknown): void {
  ensureDir(path.dirname(fp));
  fs.appendFileSync(fp, JSON.stringify(obj) + "\n", "utf-8");
}

export function writeText(fp: string, text: string): void {
  ensureDir(path.dirname(fp));
  fs.writeFileSync(fp, text, "utf-8");
}

export function safeFilename(name: string): string {
  return String(name || "")
    .replace(/[\\/:*?"<>|]/g, "_")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 180);
}
