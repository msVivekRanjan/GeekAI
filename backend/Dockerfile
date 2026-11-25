FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1

COPY requirements.txt .
RUN pip install --no-cache-dir --default-timeout=1000 --retries=10 -r requirements.txt

COPY . .
RUN sed -i 's/\r$//' docker-entrypoint.sh \
    && mkdir -p uploads/photos uploads/qrcodes \
    && chmod +x docker-entrypoint.sh \
    && useradd --create-home --shell /bin/sh appuser \
    && chown -R appuser:appuser /app

# Run as a non-root user for least privilege. No secrets are baked into the
# image; every secret is supplied at runtime through the environment.
USER appuser

ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
