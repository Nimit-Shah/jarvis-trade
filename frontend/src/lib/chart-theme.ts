function css(name: string): string {
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
    const k = (n + h / 30) % 12;
    const color = l / 100 - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
    return Math.round(255 * color).toString(16).padStart(2, "0");
  };
  return `#${f(0)}${f(8)}${f(4)}`;
}

function isChinese(): boolean {
  return (document.documentElement.lang || navigator.language || "").startsWith("zh");
}

let _cache: ReturnType<typeof buildTheme> | null = null;
let _cacheKey = "";

function buildTheme() {
  const cn = isChinese();
  const isDark = document.documentElement.classList.contains("dark");

  const successHex = toHexColor(css("--success")) || "#16A34A";
  const dangerHex = toHexColor(css("--danger")) || "#DC2626";
  const infoHex = toHexColor(css("--info")) || "#2563EB";
  const warningHex = toHexColor(css("--warning")) || "#D97706";
  const gridHex = toHexColor(css("--chart-grid")) || (isDark ? "#2C2C2C" : "#D2CBBB");
  const textHex = toHexColor(css("--chart-text")) || (isDark ? "#8E8A83" : "#5E5A52");
  const axisHex = toHexColor(css("--chart-axis")) || (isDark ? "#5C5A56" : "#A89F8F");

  // Chart-series palette (chart-1..chart-5).
  const seriesColors = ["--chart-1", "--chart-2", "--chart-3", "--chart-4", "--chart-5"]
    .map((v) => toHexColor(css(v)))
    .filter(Boolean);

  // Locale-aware candlestick colors: China = red up / green down
  const upHex = cn ? dangerHex : successHex;
  const downHex = cn ? successHex : dangerHex;

  return {
    gridColor: gridHex,
    textColor: textHex,
    axisColor: axisHex,
    upColor: upHex,
    downColor: downHex,
    maColors: seriesColors.length >= 3 ? seriesColors.slice(0, 3) : [warningHex, "#8b5cf6", infoHex],
    bollColor: "rgba(99,102,241,0.5)",
    volumeUp: upHex + "66",
    volumeDown: downHex + "66",
    infoColor: infoHex,
    warningColor: warningHex,
    tooltipBg: isDark ? "rgba(28,25,23,0.92)" : "rgba(253,251,247,0.96)",
    tooltipBorder: isDark ? "#44403C" : "#E4D9BC",
    tooltipText: isDark ? "#A8A29E" : "#4A3B33",
  };
}

export function getChartTheme() {
  const key = `${document.documentElement.className}|${document.documentElement.lang || navigator.language}`;
  if (_cache && _cacheKey === key) return _cache;
  _cache = buildTheme();
  _cacheKey = key;
  return _cache;
}
