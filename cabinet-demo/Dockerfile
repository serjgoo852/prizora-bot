FROM nginx:1.27-alpine
COPY index.html /usr/share/nginx/html/index.html
RUN sed -i -E 's/listen[[:space:]]+80;/listen 8080;/; s/listen[[:space:]]+\[::\]:80;/listen [::]:8080;/' /etc/nginx/conf.d/default.conf
EXPOSE 8080
