/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    colors: {
      primary: 'black',
      secondary: 'green',
      background: 'white',
      foreground: 'green',
      border: 'black'
    },
    extend: {},
  },
  plugins: [],
}

