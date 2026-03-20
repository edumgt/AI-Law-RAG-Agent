import fs from "fs";
import path from "path";

function ensureDir(p: string): void {
  fs.mkdirSync(p, { recursive: true });
}

export function loadCheckpoint(
  name: string,
  dir = "data/checkpoints"
): Record<string, unknown> {
  const fp = path.join(process.cwd(), dir, `${name}.json`);
  if (!fs.existsSync(fp)) return { name, createdAt: new Date().toISOString() };
  return JSON.parse(fs.readFileSync(fp, "utf-8")) as Record<string, unknown>;
}

export function saveCheckpoint(
  name: string,
  data: Record<string, unknown>,
  dir = "data/checkpoints"
): void {
  const base = path.join(process.cwd(), dir);
  ensureDir(base);
  const fp = path.join(base, `${name}.json`);
  fs.writeFileSync(
    fp,
    JSON.stringify({ ...data, name, updatedAt: new Date().toISOString() }, null, 2),
    "utf-8"
  );
}
