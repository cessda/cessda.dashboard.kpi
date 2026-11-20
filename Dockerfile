FROM python:3.13-slim AS builder

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

FROM python:3.13-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends nginx && \
    rm -f /etc/nginx/sites-enabled/default && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# NiceGUI app (served at /collective-impact/)
COPY dashboard.py .
COPY sp_analysis/ sp_analysis/
COPY data/ data/
COPY assets/ assets/

# Static Quarto dashboard (served at /validation/)
COPY --from=builder /app/dashboard.html /usr/share/nginx/html/validation/index.html
COPY --from=builder /app/dashboard_files/ /usr/share/nginx/html/validation/dashboard_files/
COPY --from=builder /app/data.csv /usr/share/nginx/html/validation/data.csv

COPY nginx.conf /etc/nginx/nginx.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV DASHBOARD_HOST=127.0.0.1 \
    DASHBOARD_RELOAD=0

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1/collective-impact/')"
CMD ["/entrypoint.sh"]
