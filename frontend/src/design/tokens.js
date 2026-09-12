/**
 * Design tokens — Retention Intelligence
 * Single source of truth for the premium dark intelligence UI.
 * Tailwind maps these via CSS variables in index.css / tokens.css.
 */

export const colors = {
  bg: {
    app: "#070b16",
    subtle: "#0c1222",
    surface: "#12192c",
    elevated: "#182238",
    interactive: "#1e2a44",
    hover: "#243052",
  },
  border: {
    subtle: "rgba(148, 163, 194, 0.12)",
    elevated: "rgba(148, 163, 194, 0.22)",
    accent: "rgba(124, 108, 255, 0.45)",
  },
  text: {
    primary: "#e8ecf7",
    secondary: "#a9b3cc",
    muted: "#7b869f",
    disabled: "#555e75",
    inverse: "#070b16",
  },
  accent: {
    primary: "#7c6cff",
    hover: "#9588ff",
    soft: "rgba(124, 108, 255, 0.16)",
    secondary: "#3d8bfd",
    glow: "rgba(124, 108, 255, 0.28)",
  },
  risk: {
    high: "#e85d75",
    highSoft: "rgba(232, 93, 117, 0.16)",
    medium: "#e8a54b",
    mediumSoft: "rgba(232, 165, 75, 0.16)",
    low: "#3dba8c",
    lowSoft: "rgba(61, 186, 140, 0.16)",
  },
  status: {
    success: "#3dba8c",
    warning: "#e8a54b",
    danger: "#e85d75",
    info: "#3d8bfd",
  },
  ai: {
    border: "rgba(124, 108, 255, 0.35)",
    soft: "rgba(124, 108, 255, 0.08)",
    glow: "rgba(61, 139, 253, 0.12)",
  },
};

/** Hex values for Recharts and canvas — keep in sync with risk tokens. */
export const RISK_CHART_COLORS = {
  HIGH: colors.risk.high,
  MEDIUM: colors.risk.medium,
  LOW: colors.risk.low,
};

export const CHART_THEME = {
  grid: "rgba(148, 163, 194, 0.12)",
  axis: colors.text.muted,
  tooltipBg: colors.bg.elevated,
  tooltipBorder: colors.border.elevated,
  tooltipText: colors.text.primary,
  barTrack: "rgba(148, 163, 194, 0.12)",
  accent: colors.accent.primary,
};

export const spacing = {
  pageX: "1.25rem",
  pageY: "1.25rem",
  section: "1.5rem",
  card: "1.25rem",
};
