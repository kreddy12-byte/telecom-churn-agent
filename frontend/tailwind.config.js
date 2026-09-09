/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "#1b2430",
          muted: "#5a6573",
          faint: "#8a93a0",
        },
        paper: {
          DEFAULT: "#eef1f5",
          raised: "#ffffff",
        },
        line: "#dce2ea",
        accent: {
          DEFAULT: "#1f4e79",
          hover: "#173c5d",
          soft: "#e7eef5",
        },
      },
      boxShadow: {
        card: "0 1px 2px rgba(27, 36, 48, 0.05), 0 1px 1px rgba(27, 36, 48, 0.04)",
      },
      borderRadius: {
        panel: "4px",
      },
      fontFamily: {
        sans: [
          "Segoe UI",
          "Helvetica Neue",
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
