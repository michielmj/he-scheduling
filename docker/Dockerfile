# Base image
FROM python:3.11-slim

# Environment variables with default values (can be overridden at runtime)
ENV POSTGRES_USER=he_scheduling
ENV POSTGRES_PASSWORD=he_scheduling
ENV POSTGRES_DB=he_scheduling
ENV POSTGRES_PORT=5432
ENV RABBITMQ_USER=he_scheduling
ENV RABBITMQ_PASSWORD=he_scheduling
ENV RABBITMQ_PORT=5672
ENV FLOWER_PORT=5555
ENV FASTAPI_PORT=8000
ENV CELERY_BROKER="amqp://${RABBITMQ_USER}:${RABBITMQ_PASSWORD}@localhost:${RABBITMQ_PORT}//"
ENV CELERY_RESULT_BACKEND="db+postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@localhost/${POSTGRES_DB}"


# Install required system dependencies with specific versions
RUN apt-get update && apt-get install -y \
    libpq-dev \
    postgresql \
    rabbitmq-server \
    && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Install Python dependencies using the `he_scheduling` package
RUN pip install he_scheduling psycopg2-binary celery flower

# Configure PostgreSQL: Initialize the database and create a user
RUN service postgresql start && \
    su - postgres -c "psql -c \"CREATE USER ${POSTGRES_USER} WITH PASSWORD '${POSTGRES_PASSWORD}';\"" && \
    su - postgres -c "psql -c \"CREATE DATABASE ${POSTGRES_DB} OWNER ${POSTGRES_USER};\"" && \
    su - postgres -c "psql -c \"ALTER USER ${POSTGRES_USER} WITH SUPERUSER;\""

# Expose necessary ports
EXPOSE ${FASTAPI_PORT} ${POSTGRES_PORT} ${RABBITMQ_PORT} ${FLOWER_PORT}

# Start-up script to launch all services
CMD /bin/bash -c "\
    service postgresql start && \
    service rabbitmq-server start && \
    rabbitmqctl add_user ${RABBITMQ_USER} ${RABBITMQ_PASSWORD} && \
    rabbitmqctl set_user_tags ${RABBITMQ_USER} administrator && \
    rabbitmqctl set_permissions -p / ${RABBITMQ_USER} '.*' '.*' '.*' && \
    celery -A he_scheduling.main.celery worker --loglevel=info & \
    celery -A he_scheduling.main.celery flower --loglevel=info & \
    uvicorn he_scheduling.main:app --host 0.0.0.0 --port=${FASTAPI_PORT}"
