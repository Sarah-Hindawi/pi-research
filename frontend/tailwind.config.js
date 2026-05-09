/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#faf8f4',
        card: '#ffffff',
        primary: {
          DEFAULT: '#1a2332',
          secondary: '#4a5568',
          tertiary: '#8b95a3',
        },
        accent: {
          navy: '#1e3a5f',
          blue: '#2c5b8e',
          'blue-soft': '#e6eef7',
          'blue-mid': '#c7d6ea',
        },
        warning: {
          DEFAULT: '#a8682f',
          soft: '#f4ead8',
        },
        success: {
          DEFAULT: '#2c7a4f',
          soft: '#e0efe5',
        },
        border: {
          soft: '#ede5d3',
          faint: '#f3ede0',
        },
      },
      fontFamily: {
        serif: ['Georgia', 'Times New Roman', 'serif'],
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
      },
      boxShadow: {
        card: '0 1px 3px rgba(26, 35, 50, 0.06), 0 1px 2px rgba(26, 35, 50, 0.04)',
        elevated: '0 4px 16px rgba(26, 35, 50, 0.08)',
      },
    },
  },
  plugins: [],
};
