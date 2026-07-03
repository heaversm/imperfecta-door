# Node container that runs the @imgly background-removal model and serves the
# tablet web app. Bookworm (glibc) so the prebuilt onnxruntime-node + sharp
# binaries load cleanly (do NOT use alpine here).
FROM node:20-bookworm-slim

WORKDIR /app

# Install deps first for layer caching.
COPY container/package.json ./
RUN npm install --omit=dev

# App source.
COPY container/ ./

ENV NODE_ENV=production
ENV PORT=8080
EXPOSE 8080

CMD ["node", "server.mjs"]
