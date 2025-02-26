/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    colors: {
      gray: {
        5: '#E0E0E0',
        25: '#FCFCFD',
        50: '#F7F9FC',
        100: '#FAFAFA',
        200: '#F0F0F0',
        300: '#E6E6E6',
        400: '#CCCCCC',
        500: '#999999',
        600: '#666666',
        700: '#4D4D4D',
        800: '#333333',
        900: '#1A1A1A',
      },
      white: '#ffffff',
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

