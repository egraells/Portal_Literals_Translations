# ──── Builder stage ───────────────────────────────────────────────────────
FROM python:3.11.12-slim AS builder

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip \
    && pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

COPY . /app

# ──── Final runtime stage ─────────────────────────────────────────────────
FROM python:3.11.12-slim AS final

# 0) Install dos2unix for line-ending sanity
RUN apt-get update \
    && apt-get install -y dos2unix \
    && rm -rf /var/lib/apt/lists/*

# 1) Create non-root user, set up the working directory, and set the environment variable to container
RUN useradd -m appuser
WORKDIR /app


# 2) Install Python deps
COPY --from=builder /wheels /wheels
COPY requirements.txt /app/
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# 3) Copy *all* of your application _and_ staticfiles, logs, scheduler, etc.
#    in one go, with the right owner, so we never need another chown later.
COPY --from=builder --chown=appuser:appuser /app /app

# Normalize all .sh scripts: convert to LF and make executable
RUN find /app -type f -name "*.sh" -exec dos2unix {} \; \
 && find /app -type f -name "*.sh" -exec chmod +x {} \;

# 4) Create media dirs and log files, then set perms
RUN mkdir -p /app/media/translation_requests/\
 && mkdir -p /app/media/review_requests/ \
 && mkdir -p /app/staticfiles \
 && touch  /app/ai_translator_frontend.log \
           /app/ai_translator_backend.log \
           /app/ai_translator_scheduler.log \
 && chown appuser:appuser /app/ai_translator_frontend.log \
                          /app/ai_translator_backend.log \
                          /app/ai_translator_scheduler.log \
 && chown -R appuser:appuser /app/media/ /app/staticfiles/ \
 && chmod -R u+rwX /app/media/ /app/staticfiles/ \
 && chmod u+rw  /app/ai_translator_frontend.log \
                /app/ai_translator_backend.log \
                /app/ai_translator_scheduler.log

# 5) Fix line endings & ensure your shell scripts are executable
# 5) Fix line endings & ensure your shell scripts are executable
RUN dos2unix /app/entrypoint.sh \
 && dos2unix /app/aitranslator_batch_process/scheduler_ai.py \
 && chmod +x /app/entrypoint.sh \
 && chmod +x /app/aitranslator_batch_process/scheduler_ai.py

# 6) Drop to the non-root user
USER appuser

EXPOSE 8000

# Depending on the value of the environment variable IS_DEVELOPMENT_ENV, 
# run the appropriate entrypoint script which is set in Docker compose files
CMD ["/app/entrypoint.sh"]
