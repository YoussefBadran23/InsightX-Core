"use client";

/**
 * <ActionChipRow> — the "what should I do next" zone under every decision chart.
 *
 * Reads `suggested_actions` from the analytics module output:
 *
 *   [
 *     { "label": "Restock 3 SKUs", "kind": "primary",   "deeplink": "/dashboard/products?..." },
 *     { "label": "Email VIPs",      "kind": "secondary", "deeplink": "/dashboard/customers" }
 *   ]
 *
 * `kind` maps to the shared semantic palette via useChartTheme, so chips
 * automatically respect dark/light mode.
 *
 * Deeplinks fire as a callback today (visual-only); we'll wire actual
 * navigation/handlers when the deep flows are built out.
 */

import { ArrowRight, Download, MoreHorizontal } from "lucide-react";
import { useChartTheme, type SemanticKind } from "../chartHelpers";

export type ActionKind = SemanticKind | "primary" | "secondary";

export interface SuggestedAction {
  /** Short label, owner-voice. e.g. "Restock 3 SKUs" */
  label: string;
  /**
   * Visual weight + colour:
   *   primary   → brand-tinted filled chip (main CTA per chart)
   *   secondary → neutral outline chip
   *   positive/warning/danger/info — semantic accent
   */
  kind?: ActionKind;
  /** Where the chip should take the user. Visual-only today. */
  deeplink?: string;
  /** Optional inline lucide icon name (rendered if present). */
  icon?: "arrow" | "download" | "more";
}

export interface ActionChipRowProps {
  actions: SuggestedAction[] | undefined | null;
  /** Optional click handler — receives the full action object. */
  onAction?: (action: SuggestedAction) => void;
  /** Hide the row entirely if no actions to show. Default true. */
  hideIfEmpty?: boolean;
  className?: string;
}

/** Map `kind` → useChartTheme semantic key. */
function kindToSemantic(kind: ActionKind | undefined): SemanticKind {
  if (!kind || kind === "primary") return "brand";
  if (kind === "secondary") return "neutral";
  return kind;
}

function IconForChip({ icon, size = 12 }: { icon?: SuggestedAction["icon"]; size?: number }) {
  if (icon === "download") return <Download style={{ width: size, height: size }} />;
  if (icon === "more") return <MoreHorizontal style={{ width: size, height: size }} />;
  // default = arrow
  return <ArrowRight style={{ width: size, height: size }} />;
}

export function ActionChipRow({
  actions,
  onAction,
  hideIfEmpty = true,
  className = "",
}: ActionChipRowProps) {
  const t = useChartTheme();

  const list = (actions || []).filter((a) => a && a.label);
  if (list.length === 0 && hideIfEmpty) return null;

  return (
    <div className={`flex flex-wrap items-center gap-2 ${className}`}>
      {list.map((a, idx) => {
        const sem = kindToSemantic(a.kind);
        const isPrimary = a.kind === "primary" || (idx === 0 && !a.kind);
        const accent = t.semantic[sem];
        const tint = t.semanticSoft[sem];

        const buttonStyle = isPrimary
          ? {
              background: accent,
              color: "#FFFFFF",
              border: `1px solid ${accent}`,
            }
          : {
              background: tint,
              color: accent,
              border: `1px solid ${accent}40`,
            };

        return (
          <button
            key={`${a.label}-${idx}`}
            type="button"
            onClick={() => onAction?.(a)}
            className="text-[11px] font-semibold px-2.5 py-1.5 rounded-md inline-flex items-center gap-1.5 transition-all hover:-translate-y-0.5 hover:shadow-sm"
            style={buttonStyle}
            title={a.deeplink ?? a.label}
          >
            <IconForChip icon={a.icon} size={12} />
            <span>{a.label}</span>
          </button>
        );
      })}
    </div>
  );
}
