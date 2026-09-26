/** Cellar & Ivory design system. Colors are CSS variables so /theme.css can apply company colors. */
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;
module.exports = {
  content: ["./app/templates/**/*.html", "./app/static/app.js", "./app/branding.py"],
  // classes built from data at render time (brand slugs, bar widths, status names)
  safelist: [
    { pattern: /^brand-(zoa|henrys|fever-tree|naked-life)$/ },
    { pattern: /^edge-(zoa|henrys|fever-tree|naked-life|danger|warning|success|muted)$/ },
    { pattern: /^w-pct-\d+$/ },
    { pattern: /^pill-(success|danger|warning|info|muted|accent)$/ },
    { pattern: /^toast-(ok|warn|bad|info|win)$/ },
  ],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    extend: {
      colors: {
        background: v("background"), card: v("card"), raised: v("raised"), foreground: v("foreground"),
        muted: { DEFAULT: v("muted"), foreground: v("muted-foreground") },
        border: v("border"), input: v("input"),
        primary: { DEFAULT: v("primary"), foreground: "rgb(255 255 255 / <alpha-value>)", text: v("primary-text") },
        accent: { DEFAULT: v("accent"), text: v("accent-text") },
        success: v("success"), danger: v("danger"), warning: v("warning"), info: v("info"),
        brand: { zoa: "#0F6B78", henrys: "#7A1F2B", fevertree: "#8A5A19", nakedlife: "#2F7D32" },
      },
      fontFamily: {
        sans: ["InterVariable", "Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        display: ["FrauncesVariable", "Fraunces", "Georgia", "serif"],
      },
      borderRadius: { xl: "14px", "2xl": "18px", "3xl": "24px" },
      boxShadow: {
        card: "0 1px 2px rgb(28 25 23 / .05), 0 6px 20px -8px rgb(28 25 23 / .10)",
        lift: "0 2px 4px rgb(28 25 23 / .06), 0 16px 32px -12px rgb(28 25 23 / .22)",
        bar: "0 -8px 24px -12px rgb(28 25 23 / .25)",
      },
      keyframes: {
        rise: { "0%": { opacity: 0, transform: "translateY(6px)" }, "100%": { opacity: 1, transform: "none" } },
        pop: { "0%": { transform: "scale(.9)", opacity: 0 }, "60%": { transform: "scale(1.04)" }, "100%": { transform: "scale(1)", opacity: 1 } },
        shimmer: { "100%": { transform: "translateX(100%)" } },
      },
      animation: { rise: "rise .2s ease-out both", pop: "pop .25s ease-out both" },
    },
  },
  plugins: [],
};
