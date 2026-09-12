/**
 * Design tokens — Retention Intelligence
 * Single source of truth for the premium light SaaS UI.
 * Tailwind maps these via CSS variables in index.css / tokens.css.
 */

export const colors = {
  bg: {
    app: "#f7f8fc",
    subtle: "#f8f9fd",
    surface: "#ffffff",
    elevated: "#ffffff",
    interactive: "#f8f9fd",
    hover: "#f0f2f8",
    lavender: "#f3f1ff",
    blue: "#eef4ff",
  },
  border: {
    subtle: "#e7eaf2",
    elevated: "#d9dee9",
    accent: "rgba(99, 91, 255, 0.35)",
  },
  text: {
    primary: "#172033",
    secondary: "#64708a",
    muted: "#8a94a8",
    disabled: "#a8b0c0",
    inverse: "#ffffff",
  },
  accent: {
    primary: "#635bff",
    hover: "#4f46e5",
    soft: "#f3f1ff",
    secondary: "#3b82f6",
    glow: "rgba(99, 91, 255, 0.14)",
  },
  risk: {
    high: "#d1435b",
    highSoft: "#fdecee",
    medium: "#c47d1a",
    mediumSoft: "#fff6e8",
    low: "#1f9a72",
    lowSoft: "#e8f8f1",
  },
  status: {
    success: "#1f9a72",
    warning: "#c47d1a",
    danger: "#d1435b",
    info: "#3b82f6",
  },
  ai: {
    border: "rgba(99, 91, 255, 0.22)",
    soft: "#f3f1ff",
    glow: "rgba(59, 130, 246, 0.1)",
  },
};

/** Hex values for Recharts and canvas — keep in sync with risk tokens. */
export const RISK_CHART_COLORS = {
  HIGH: colors.risk.high,
  MEDIUM: colors.risk.medium,
  LOW: colors.risk.low,
};

export const CHART_THEME = {
  grid: "#e7eaf2",
  axis: colors.text.muted,
  tooltipBg: colors.bg.surface,
  tooltipBorder: colors.border.elevated,
  tooltipText: colors.text.primary,
  barTrack: "#eef0f6",
  accent: colors.accent.primary,
};

export const spacing = {
  pageX: "1.25rem",
  pageY: "1.25rem",
  section: "1.5rem",
  card: "1.25rem",
};
