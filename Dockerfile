FROM nginx:alpine
COPY dashboard.html /usr/share/nginx/html/index.html
COPY data.csv /usr/share/nginx/html/data.csv
EXPOSE 80
