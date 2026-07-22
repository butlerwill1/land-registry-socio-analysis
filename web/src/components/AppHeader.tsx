import { Database, MapPinned, TriangleAlert } from "lucide-react";
import type { AppMetadata } from "../types";

export function AppHeader({ metadata }: { metadata: AppMetadata }) {
  return (
    <header className="app-header">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">
          <MapPinned size={21} strokeWidth={2} />
        </span>
        <span>London Flat Atlas</span>
      </div>
      <div className="header-meta">
        <span className="source-line">
          <Database size={15} aria-hidden="true" />
          Land Registry 1995-{metadata.latestYear} · IMD 2025
        </span>
        <span className="partial-note">
          <TriangleAlert size={14} aria-hidden="true" />
          {metadata.latestYear} is partial
        </span>
      </div>
    </header>
  );
}
