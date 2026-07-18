/** @type {import('tailwindcss').Config} */
export default {
  darkMode: 'class',
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50: '#eef4ff',
          100: '#dfe8ff',
          200: '#c2d3ff',
          300: '#9ab3ff',
          400: '#6d87ff',
          500: '#4a5cf5',
          600: '#3a3fd9',
          700: '#3131b0',
          800: '#2b2c8c',
          900: '#282a70',
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
