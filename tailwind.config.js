/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./templates/**/*.html", "./apps/**/*.py", "./static/js/**/*.js"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"] },
      colors: {
        brand: {
          50: "#f0fdfa", 100: "#ccfbf1", 200: "#99f6e4", 300: "#5eead4", 400: "#2dd4bf",
          500: "#14b8a6", 600: "#0d9488", 700: "#0f766e", 800: "#115e59", 900: "#134e4a", 950: "#042f2e",
        },
        ink: "#0f172a",
        mist: "#f6faf9",
      },
    },
  },
  plugins: [require("@tailwindcss/forms")],
};
