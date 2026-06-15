import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: "#10223E",
        "navy-deep": "#09172C",
        ink: "#1A2638",
        accent: "#C5A15A",
        "accent-soft": "#E8D9B5",
        ice: "#DCE6F7",
        mist: "#F4F7FB",
        success: "#1F8A5B",
        warning: "#C98311",
        danger: "#B94C3D",
        line: "#D6DEEA"
      }
    }
  },
  plugins: []
};
export default config;
