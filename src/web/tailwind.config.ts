import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        navy: "#1E2761",
        accent: "#F96167",
        ice: "#CADCFC"
      }
    }
  },
  plugins: []
};
export default config;
