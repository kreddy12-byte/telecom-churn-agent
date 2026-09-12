/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // Legacy semantic names remapped to the premium dark system
        ink: {
          DEFAULT: "rgb(var(--ri-text-rgb) / <alpha-value>)",
          muted: "rgb(var(--ri-text-secondary-rgb) / <alpha-value>)",
          faint: "rgb(var(--ri-text-muted-rgb) / <alpha-value>)",
          disabled: "var(--ri-text-disabled)",
          inverse: "var(--ri-text-inverse)",
        },
        paper: {
          DEFAULT: "rgb(var(--ri-bg-app-rgb) / <alpha-value>)",
          subtle: "rgb(var(--ri-bg-subtle-rgb) / <alpha-value>)",
          raised: "rgb(var(--ri-surface-rgb) / <alpha-value>)",
        },
        line: {
          DEFAULT: "var(--ri-border)",
          elevated: "var(--ri-border-elevated)",
        },
        accent: {
          DEFAULT: "rgb(var(--ri-accent-rgb) / <alpha-value>)",
          hover: "var(--ri-accent-hover)",
          soft: "var(--ri-accent-soft)",
          secondary: "rgb(var(--ri-accent-secondary-rgb) / <alpha-value>)",
          glow: "var(--ri-accent-glow)",
        },
        surface: {
          DEFAULT: "rgb(var(--ri-surface-rgb) / <alpha-value>)",
          elevated: "rgb(var(--ri-surface-elevated-rgb) / <alpha-value>)",
          interactive: "rgb(var(--ri-surface-interactive-rgb) / <alpha-value>)",
          muted: "rgb(var(--ri-bg-subtle-rgb) / <alpha-value>)",
          hover: "rgb(var(--ri-surface-hover-rgb) / <alpha-value>)",
        },
        risk: {
          high: "rgb(var(--ri-risk-high-rgb) / <alpha-value>)",
          "high-soft": "var(--ri-risk-high-soft)",
          medium: "rgb(var(--ri-risk-medium-rgb) / <alpha-value>)",
          "medium-soft": "var(--ri-risk-medium-soft)",
          low: "rgb(var(--ri-risk-low-rgb) / <alpha-value>)",
          "low-soft": "var(--ri-risk-low-soft)",
        },
        success: {
          DEFAULT: "rgb(var(--ri-success-rgb) / <alpha-value>)",
          soft: "var(--ri-success-soft)",
        },
        warning: {
          DEFAULT: "rgb(var(--ri-warning-rgb) / <alpha-value>)",
          soft: "var(--ri-warning-soft)",
        },
        danger: {
          DEFAULT: "rgb(var(--ri-danger-rgb) / <alpha-value>)",
          soft: "var(--ri-danger-soft)",
        },
        info: {
          DEFAULT: "rgb(var(--ri-info-rgb) / <alpha-value>)",
          soft: "var(--ri-info-soft)",
        },
        ai: {
          border: "var(--ri-ai-border)",
          soft: "var(--ri-ai-soft)",
          glow: "var(--ri-ai-glow)",
        },
      },
      boxShadow: {
        card: "var(--ri-shadow-md)",
        elevated: "var(--ri-shadow-lg)",
        glow: "var(--ri-shadow-glow)",
        sm: "var(--ri-shadow-sm)",
      },
      borderRadius: {
        panel: "var(--ri-radius-md)",
        control: "var(--ri-radius-sm)",
        sheet: "var(--ri-radius-lg)",
      },
      fontFamily: {
        sans: [
          '"Plus Jakarta Sans"',
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
        display: [
          '"Plus Jakarta Sans"',
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
        mono: [
          '"JetBrains Mono"',
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      fontSize: {
        "kpi": ["1.75rem", { lineHeight: "1.1", letterSpacing: "-0.03em", fontWeight: "600" }],
        "page": ["1.5rem", { lineHeight: "1.25", letterSpacing: "-0.025em", fontWeight: "600" }],
      },
      transitionTimingFunction: {
        ri: "var(--ri-ease)",
      },
      transitionDuration: {
        fast: "var(--ri-duration-fast)",
        ri: "var(--ri-duration)",
        slow: "var(--ri-duration-slow)",
      },
      keyframes: {
        "ri-fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "ri-scale-in": {
          from: { opacity: "0", transform: "scale(0.98)" },
          to: { opacity: "1", transform: "scale(1)" },
        },
        "ri-route-enter": {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "ri-shimmer": {
          "0%": { backgroundPosition: "100% 0" },
          "100%": { backgroundPosition: "-100% 0" },
        },
      },
      animation: {
        "ri-fade-in": "ri-fade-in var(--ri-duration) var(--ri-ease)",
        "ri-scale-in": "ri-scale-in var(--ri-duration) var(--ri-ease)",
        "ri-route-enter": "ri-route-enter var(--ri-duration) var(--ri-ease)",
        "ri-shimmer": "ri-shimmer 1.4s ease-in-out infinite",
      },
      maxWidth: {
        content: "72rem",
      },
    },
  },
  plugins: [],
};
