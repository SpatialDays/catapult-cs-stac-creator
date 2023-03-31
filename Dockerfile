FROM python:3.9-slim-buster

COPY requirements.txt /tmp/
RUN pip install -r /tmp/requirements.txt
RUN pip install redis

RUN mkdir -p /src
COPY src/ /src/
RUN pip install -e /src
ENV PYTHONDONTWRITEBYTECODE=1
CMD python /src/sac_stac/entrypoints/nats_eventconsumer.py
