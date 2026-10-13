import colors from 'tailwindcss/colors'

/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Design system "Chợ": one brand colour for actions, one colour for prices.
        // `primary` keeps its name so existing classes re-theme without a rewrite.
        primary: {
          50: '#F1F8F5',
          100: '#E3F1EC',
          200: '#C4E2D6',
          300: '#93CBB8',
          400: '#54A68C',
          500: '#1F8068',
          600: '#0E6B55',
          700: '#0A5242',
          800: '#083F33',
          900: '#062F27',
          950: '#031C17',
        },
        brand: {
          DEFAULT: '#0E6B55',
          strong: '#0A5242',
          soft: '#E3F1EC',
        },
        price: '#D23F1F',
        danger: { DEFAULT: '#A32E14', soft: '#FBE9E5' },
        warning: { DEFAULT: '#B26A00', soft: '#FDF1DC' },
        ink: '#15171A',
        muted: '#6B716A',
        line: '#DFE2DC',
        ground: '#F3F4F1',
        // Keep the full Tailwind scale so emerald-100 etc. still exist.
        emerald: { ...colors.emerald, DEFAULT: '#0E6B55' },
        mint: '#E3F1EC',
        sunflower: '#B26A00',
      },
      boxShadow: {
        lift: '0 12px 32px rgba(21, 23, 26, 0.14)',
        soft: 'none',
      },
      borderRadius: {
        card: '10px',
        panel: '16px',
      },
      fontFamily: {
        sans: ['"Be Vietnam Pro"', 'Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
