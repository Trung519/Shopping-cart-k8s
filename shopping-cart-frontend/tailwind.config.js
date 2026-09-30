/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
          950: '#172554',
        },
        ink: '#0f172a',
        emerald: '#0f9f8f',
        mint: '#2dd4bf',
        sunflower: '#f59e0b',
      },
      boxShadow: {
        lift: '0 18px 45px rgba(15, 23, 42, 0.12)',
        soft: '0 8px 24px rgba(37, 99, 235, 0.08)',
      },
      borderRadius: {
        card: '0.875rem',
        panel: '1.125rem',
      },
      fontFamily: {
        sans: ['"Be Vietnam Pro"', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
