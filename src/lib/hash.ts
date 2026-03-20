import { createHash } from "crypto";

export function sha256(text: string): string {
  return createHash("sha256").update(String(text || ""), "utf8").digest("hex");
}
