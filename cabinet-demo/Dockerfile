FROM nginx:1.27-alpine
COPY index.html /usr/share/nginx/html/index.html
RUN cat > /etc/nginx/conf.d/default.conf <<'EOF'
server {
    listen 8080;
    listen [::]:8080;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;
    location / { try_files $uri $uri/ =404; }
}
EOF
EXPOSE 8080
