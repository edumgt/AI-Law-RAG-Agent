import fs from "fs";
import path from "path";

export interface ManifestDocument {
  doc_id: string;
  doc_type: string;
  title: string;
  jurisdiction?: string;
  effective_date?: string | null;
  version?: number;
  path: string;
  allowed_roles?: string[];
  source_url?: string | null;
  meta?: Record<string, unknown>;
}

export interface ManifestDefault {
  jurisdiction?: string;
  language?: string;
  version_strategy?: string;
  allowed_roles?: string[];
}

export interface Manifest {
  schema?: number;
  default?: ManifestDefault;
  documents?: ManifestDocument[];
}

export function loadManifest(manifestPath = "data/manifest.json"): Manifest | null {
  const abs = path.isAbsolute(manifestPath)
    ? manifestPath
    : path.join(process.cwd(), manifestPath);
  if (!fs.existsSync(abs)) return null;
  const raw = fs.readFileSync(abs, "utf-8");
  return JSON.parse(raw) as Manifest;
}
