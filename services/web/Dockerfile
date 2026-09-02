FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ARG VITE_BACK_API_URL
ENV VITE_BACK_API_URL=${VITE_BACK_API_URL}

RUN npm run build

FROM nginx:1.27-alpine AS production

ENV API_UPSTREAM=http://api:8080
ENV NGINX_ENVSUBST_FILTER=API_UPSTREAM

COPY nginx.conf /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --spider --quiet http://localhost/ || exit 1

CMD ["nginx", "-g", "daemon off;"]