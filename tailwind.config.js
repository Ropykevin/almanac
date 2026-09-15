/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/templates/**/*.html", "./app/static/js/**/*.js"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0fdfa",
          100: "#ccfbf1",
          600: "#0d9488",
          700: "var(--brand-primary, #0f766e)",
          800: "var(--brand-primary, #0f766e)",
          900: "var(--brand-primary, #0f766e)",
        },
        ink: {
          950: "#0c1210",
          900: "#14201c",
          700: "#2f3d38",
        },
      },
      fontFamily: {
        display: ['"Source Serif 4"', "Georgia", "serif"],
        sans: ['"DM Sans"', "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
