# Runs the daily decision job. Build once; schedule `docker compose run --rm runner` at 15:15 IST
# from the machine whose static IP is registered with Upstox.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 TZ=Asia/Kolkata
WORKDIR /app
RUN useradd --create-home --uid 10001 app
COPY pyproject.toml README.md ./
COPY src ./src
COPY configs ./configs
RUN pip install .
USER app
ENV OPTLAB_ROOT=/app
VOLUME ["/app/data", "/app/journal", "/home/app/.optlab"]
ENTRYPOINT ["optlab"]
CMD ["live", "run", "--mode", "paper"]
