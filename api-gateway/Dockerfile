FROM nginx:1.27-alpine

# Eliminar config por defecto e instalar curl para healthcheck
RUN rm /etc/nginx/conf.d/default.conf && apk add --no-cache curl

COPY nginx.conf /etc/nginx/nginx.conf
COPY conf.d/ /etc/nginx/conf.d/

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -fsS http://localhost/health/gateway || exit 1
