import { Database, MapPinned, TriangleAlert } from "lucide-react";
import type { AppMetadata } from "../types";

export function AppHeader({ metadata }: { metadata: AppMetadata }) {
  const dataAsOf = new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(`${metadata.dataAsOf}T00:00:00Z`));

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
        {metadata.latestYearIsPartial && (
          <span
            className="partial-note"
            title="Recent HM Land Registry totals increase as later registrations arrive."
          >
            <TriangleAlert size={14} aria-hidden="true" />
            {metadata.latestYear} partial - sales recorded to {dataAsOf}
          </span>
        )}
      </div>
    </header>
  );
}
