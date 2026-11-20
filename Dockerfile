FROM python:3.12-slim

LABEL description="Indy - checks whether a signed deal is ready to become a project"

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5112

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5112/health')" || exit 1

CMD ["python", "-m", "indy.main", "serve"]
