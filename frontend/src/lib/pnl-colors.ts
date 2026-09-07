/**
 * P&L semantic colors for the Options Lab charts.
 *
 * getChartTheme().upColor/downColor are DIRECTION colors — they flip under the
 * Chinese red-up convention. P&L must read green=profit / red=loss in every
 * locale, so this helper reads the raw --success/--danger design tokens
 * instead (same CSS variables chart-theme parses, but unflipped).
 */

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

function toHexColor(val: string): string {
  if (!val) return "";
  const trimmed = val.trim();
  if (trimmed.startsWith("#")) return trimmed;
  if (trimmed.startsWith("rgb")) return trimmed;
  const [h, s, l] = trimmed.split(/\s+/).map(parseFloat);
  if (isNaN(h)) return trimmed;
  const a = (s / 100) * Math.min(l / 100, 1 - l / 100);
  const f = (n: number) => {
    const kk = (n + h / 30) % 12;
    const color = l / 100 - a * Math.max(Math.min(kk - 3, 9 - kk, 1), -1);
    return Math.round(255 * color).toString(16).padStart(2, "0");
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

export interface PnlColors {
  profit: string;
  loss: string;
  neutral: string;
}

export function getPnlColors(): PnlColors {
  const isDark = document.documentElement.classList.contains("dark");
  return {
    profit: toHexColor(cssVar("--success")) || (isDark ? "#22C55E" : "#16A34A"),
    loss: toHexColor(cssVar("--danger")) || (isDark ? "#EF4444" : "#DC2626"),
    neutral: isDark ? "#1C1C1C" : "#F4EFE4",
  };
}
