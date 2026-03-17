/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        // SABIC color palette
        navy: {
          DEFAULT: '#003F6B',
          dark: '#002147',
          light: '#005a99',
          surface: '#1A2B3C',
          card: '#1E3347',
          border: '#234060',
        },
        sabic: {
          cyan: '#00B4CC',
          'cyan-light': '#33C8DE',
          'cyan-dark': '#008FA3',
          yellow: '#F5C800',
          'yellow-dark': '#C9A200',
          red: '#E30613',
          'red-dark': '#B0040F',
          'gray-1': '#4A4A4A',
          'gray-2': '#9E9E9E',
          'gray-3': '#D4D4D4',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
