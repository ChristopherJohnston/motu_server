# Use the official lightweight Python image.
# https://hub.docker.com/_/python
FROM python:3.11-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED=True

# Copy local code to the container image.
ENV APP_HOME=/app
WORKDIR $APP_HOME
COPY . .

# Install production dependencies.
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8080

CMD ["python", "run", "--no-register", "--datastore", "./datastore.json"]