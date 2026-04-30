FROM python:3.11-slim

WORKDIR /app

COPY demo/requirements.txt demo/requirements.txt
RUN pip install --no-cache-dir -r demo/requirements.txt

COPY demo demo

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["python", "-m", "demo.run_demo"]
