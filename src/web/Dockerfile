FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json ./
RUN npm install --no-audit --no-fund

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_PUBLIC_API_BASE_URL=""
ENV NEXT_PUBLIC_AZURE_TENANT_ID="2864e36c-40de-4ccf-93a2-ba4b0cf51826"
ENV API_BACKEND_URL="https://ca-api-ljiihlefub3f4.blackforest-6516eaf5.swedencentral.azurecontainerapps.io"
RUN chmod -R +x node_modules/.bin && npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV PORT=3000
ENV API_BACKEND_URL="https://ca-api-ljiihlefub3f4.blackforest-6516eaf5.swedencentral.azurecontainerapps.io"
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
