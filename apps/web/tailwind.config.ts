import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
    "./src/lib/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["IBM Plex Sans", "Segoe UI", "ui-sans-serif", "sans-serif"]
      },
      colors: {
        brand: {
          50: "#edf7ff",
          100: "#d6edff",
          200: "#b5ddff",
          300: "#84c6ff",
          400: "#4ea6ff",
          500: "#2286ff",
          600: "#0066f5",
          700: "#0052d2",
          800: "#0447aa",
          900: "#0b3f84"
        }
      }
    }
  },
  plugins: []
};

export default config;
