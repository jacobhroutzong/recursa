FROM python:3.11-slim
WORKDIR /app
COPY recursa /app/recursa
COPY apps/studio /app/apps/studio
COPY traces/public /app/runs
COPY public/progress.json /app/public/progress.json
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 1000
EXPOSE 7860
CMD ["python", "-m", "recursa.server", "--host", "0.0.0.0", "--port", "7860"]
