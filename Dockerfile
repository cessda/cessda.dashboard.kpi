FROM python:3.11-slim AS builder

RUN apt-get update && apt-get install -y curl && \
    curl -LO https://github.com/quarto-dev/quarto-cli/releases/download/v1.6.42/quarto-1.6.42-linux-amd64.deb && \
    dpkg -i quarto-1.6.42-linux-amd64.deb && \
    rm quarto-1.6.42-linux-amd64.deb && \
    apt-get clean

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN python -m ipykernel install --name sp-analysis --display-name "sp-analysis"
RUN quarto render dashboard.qmd --verbose
RUN ls -la /app/

FROM nginx:alpine
COPY --from=builder /app/dashboard.html /usr/share/nginx/html/index.html
COPY --from=builder /app/dashboard_files/ /usr/share/nginx/html/dashboard_files/
COPY --from=builder /app/data.csv /usr/share/nginx/html/data.csv
EXPOSE 80
