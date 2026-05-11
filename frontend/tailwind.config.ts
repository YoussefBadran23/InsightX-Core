import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        // Primary — blue brand from starter
        primary: {
          DEFAULT: "#137fec",
          50: "#eff6ff",
          100: "#dbeafe",
          200: "#bfdbfe",
          300: "#93c5fd",
          400: "#60a5fa",
          500: "#137fec",
          600: "#2563eb",
          700: "#1d4ed8",
          800: "#1e40af",
          900: "#1e3a8a",
        },
        // Surfaces — wired to CSS variables in globals.css so they flip
        // automatically when `.dark` is on <html>. The fallback colors after
        // the slash are the light-mode defaults so Tailwind's default plugin
        // gets a real value for any utility that needs one statically.
        surface: {
          DEFAULT:  "var(--surface, #f8fafc)",
          elevated: "var(--surface-elevated, #ffffff)",
          card:     "var(--surface-card, #ffffff)",
          border:   "var(--surface-border, #e2e8f0)",
          hover:    "var(--surface-hover, #f1f5f9)",
        },
        // Page background — `bg-background-light` / `bg-background-dark`
        // are used by the dashboard layout's root flex container.
        background: {
          light: "#f8fafc",
          dark:  "#0f0f1a",
        },
        // Semantic
        success: { DEFAULT: "#10b981", light: "#d1fae5", dark: "#065f46" },
        warning: { DEFAULT: "#f59e0b", light: "#fef3c7", dark: "#92400e" },
        danger:  { DEFAULT: "#ef4444", light: "#fee2e2", dark: "#7f1d1d" },
        info:    { DEFAULT: "#3b82f6", light: "#dbeafe", dark: "#1e3a5f" },
        // Text
        text: {
          primary:   "#0f172a",
          secondary: "#475569",
          muted:     "#94a3b8",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      fontSize: {
        "2xs": ["0.65rem", { lineHeight: "1rem" }],
      },
      borderRadius: {
        "4xl": "2rem",
      },
      boxShadow: {
        glow:         "0 0 20px rgba(99, 102, 241, 0.3)",
        "glow-sm":    "0 0 10px rgba(99, 102, 241, 0.2)",
        "glow-green": "0 0 12px rgba(16, 185, 129, 0.3)",
        "glow-red":   "0 0 12px rgba(239, 68, 68, 0.3)",
        "glow-amber": "0 0 12px rgba(245, 158, 11, 0.3)",
        card: "0 4px 24px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.2)",
        "card-hover": "0 8px 40px rgba(0,0,0,0.5), 0 2px 4px rgba(0,0,0,0.3)",
      },
      backgroundImage: {
        "gradient-radial":   "radial-gradient(var(--tw-gradient-stops))",
        "gradient-conic":    "conic-gradient(from 180deg at 50% 50%, var(--tw-gradient-stops))",
        "gradient-primary":  "linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)",
        "gradient-dark":     "linear-gradient(180deg, #0f0f1a 0%, #16162a 100%)",
        "gradient-card":     "linear-gradient(135deg, rgba(99,102,241,0.05) 0%, rgba(139,92,246,0.02) 100%)",
        "mesh-primary":      "radial-gradient(ellipse at 20% 50%, rgba(99,102,241,0.15) 0%, transparent 50%), radial-gradient(ellipse at 80% 20%, rgba(139,92,246,0.1) 0%, transparent 50%)",
      },
      animation: {
        "fade-in":      "fadeIn 0.4s ease-out",
        "slide-up":     "slideUp 0.4s ease-out",
        "slide-in-left":"slideInLeft 0.3s ease-out",
        "scale-in":     "scaleIn 0.2s ease-out",
        "shimmer":      "shimmer 1.5s infinite",
        "pulse-slow":   "pulse 3s cubic-bezier(0.4,0,0.6,1) infinite",
        "spin-slow":    "spin 3s linear infinite",
        "bounce-slow":  "bounce 2s infinite",
        "glow-pulse":   "glowPulse 2s ease-in-out infinite",
      },
      keyframes: {
        fadeIn:      { from: { opacity: "0" },                       to: { opacity: "1" } },
        slideUp:     { from: { opacity: "0", transform: "translateY(16px)" }, to: { opacity: "1", transform: "translateY(0)" } },
        slideInLeft: { from: { opacity: "0", transform: "translateX(-16px)" }, to: { opacity: "1", transform: "translateX(0)" } },
        scaleIn:     { from: { opacity: "0", transform: "scale(0.95)" }, to: { opacity: "1", transform: "scale(1)" } },
        shimmer: {
          "0%":   { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition:  "200% 0" },
        },
        glowPulse: {
          "0%, 100%": { boxShadow: "0 0 10px rgba(99,102,241,0.2)" },
          "50%":       { boxShadow: "0 0 25px rgba(99,102,241,0.5)" },
        },
      },
    },
  },
  plugins: [],
};

export default config;
