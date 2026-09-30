import animate from "tailwindcss-animate";
import defaultTheme from "tailwindcss/defaultTheme";

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", ...defaultTheme.fontFamily.sans],
        mono: ["JetBrains Mono", ...defaultTheme.fontFamily.mono],
      },
      colors: {
        brand: {
          50: "#eef3ff",
          100: "#dce6fe",
          200: "#c0d2fe",
          300: "#94b3fc",
          400: "#6189f8",
          500: "#3c63f3",
          600: "#2645e8",
          700: "#1d36d5",
          800: "#1e2fad",
          900: "#1e2d88",
          950: "#0b1530",
        },
      },
      keyframes: {
        "verify-slide": {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(300%)" },
        },
      },
      animation: {
        "verify-slide": "verify-slide 1.4s ease-in-out infinite",
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(16 24 40 / 0.04), 0 1px 3px 0 rgb(16 24 40 / 0.04)",
        lift: "0 4px 6px -2px rgb(16 24 40 / 0.04), 0 12px 24px -6px rgb(16 24 40 / 0.10)",
      },
    },
  },
  plugins: [animate],
};
