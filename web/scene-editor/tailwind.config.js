/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "-apple-system", "BlinkMacSystemFont", "\"Segoe UI\"", "sans-serif"],
      },
      colors: {
        "editor-surface": "#0f172a",
        "editor-panel": "#111827",
        "editor-accent": "#38bdf8",
      },
    },
  },
  plugins: [],
};
