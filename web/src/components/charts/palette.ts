// Chart palette: the dataviz reference categorical palette in its validated fixed order
// (validated against this app's white card surface: all hard gates pass; slots 3-5 are below 3:1
// contrast, so every chart ships with a legend and a data table). Brand green is UI chrome only.
export const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];

export const CHART = {
  surface: "#ffffff",
  grid: "#e1e0d9",
  axis: "#c3c2b7",
  muted: "#898781",
  ink: "#0b0b0b",
  secondary: "#52514e",
};

/** Colour follows the entity, never its rank: fixed keys get fixed slots. */
export const SCOPE_COLORS: Record<string, string> = { "Scope 1": SERIES[0], "Scope 2": SERIES[1], "Scope 3": SERIES[2] };

export function compact(n: number): string {
  const abs = Math.abs(n);
  if (abs >= 1e9) return `${+(n / 1e9).toFixed(1)}B`;
  if (abs >= 1e6) return `${+(n / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${+(n / 1e3).toFixed(1)}K`;
  return `${+n.toFixed(2)}`;
}
