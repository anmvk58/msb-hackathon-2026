FROM nginx:1.27-alpine
COPY deploy/production/mobile.nginx.conf.template /etc/nginx/templates/default.conf.template
COPY frontend-mobile/src /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=10s --timeout=3s --retries=3 CMD wget -q -O /dev/null http://127.0.0.1/health || exit 1
