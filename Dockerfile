# The NORMA-O explorer on the residential lease, as a container (e.g. a Hugging Face Space).
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
RUN useradd -m -u 1000 user
WORKDIR /home/user/app
# NORMA-O 2.0 from its release tag, then Flask for the explorer
COPY requirements.txt requirements.txt
COPY web/requirements.txt web/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r web/requirements.txt
COPY --chown=user . .
USER user
ENV HOST=0.0.0.0 PORT=7860 PYTHONUNBUFFERED=1
EXPOSE 7860
WORKDIR /home/user/app/web
CMD ["python", "app.py"]
