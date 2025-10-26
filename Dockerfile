FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY neural_engine ./neural_engine

# This Dockerfile is for the application itself.
# To run the application, you would typically have a main.py or similar entrypoint.
# For now, we'll just have it tail /dev/null to keep the container running.
CMD ["tail", "-f", "/dev/null"]
