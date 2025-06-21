/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
      "./index.html",
      "./src/**/*.{js,jsx,ts,tsx}"
    ],
    theme: {
      extend: {
        colors: {
          'amor-pink': '#FBE9F0',
          'amor-accent': '#D6336C',
          'amor-dark': '#951944',
        },
        fontFamily: {
          'decor': ['Montserrat', 'Arial', 'sans-serif'],
        },
      },
    },
    plugins: [],
  }
  