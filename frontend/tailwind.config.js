/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        // Base palette (per project spec)
        mint:     { 100: '#E6FBF6', 300: '#A7F1DE', 500: '#5EE6C8', 700: '#2EB99B' },
        lavender: { 100: '#F2EEFF', 300: '#D5C5FF', 500: '#B79CFF', 700: '#8A6DF0' },
        orange:   { 300: '#FFC59A', 500: '#FFA552', 700: '#FF7A45' },
        // Per-page accent colors
        accent: {
          dashboard:   '#5EE6C8',
          stability:   '#4DA8FF',
          failure:     '#FF7A45',
          meter:       '#B79CFF',
          recommend:   '#6FE38A',
          telemetry:   '#4DE2F0',
          etl:         '#FFA552',
          agent:       '#9D8BFF',
          timeline:    '#FFD166',
          heatmap:     '#F47B7B',
          query:       '#5EE6C8',
        },
        ink: { 900: '#0F1B2D', 700: '#1A2238', 500: '#3F4B66', 300: '#7F8AA3' },
      },
      fontFamily: {
        sans: ['"Inter"', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      boxShadow: {
        glass:  '0 8px 32px 0 rgba(15, 27, 45, 0.08)',
        glow:   '0 0 24px 4px rgba(94, 230, 200, 0.35)',
        card:   '0 4px 16px 0 rgba(15, 27, 45, 0.06)',
        'card-hover': '0 12px 32px 0 rgba(15, 27, 45, 0.12)',
      },
      backdropBlur: { xs: '2px' },
      keyframes: {
        'fade-up': {
          '0%':   { opacity: 0, transform: 'translateY(8px)' },
          '100%': { opacity: 1, transform: 'translateY(0)' },
        },
        'shimmer': {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'pulse-glow': {
          '0%,100%': { boxShadow: '0 0 0 0 rgba(94,230,200,0.5)' },
          '50%':     { boxShadow: '0 0 24px 6px rgba(94,230,200,0.35)' },
        },
      },
      animation: {
        'fade-up':    'fade-up 0.4s ease-out both',
        'shimmer':    'shimmer 2s linear infinite',
        'pulse-glow': 'pulse-glow 2.4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
