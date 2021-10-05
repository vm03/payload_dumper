FROM python:3.9.7-alpine3.14

RUN apk upgrade \
      && apk add xz

WORKDIR /app
VOLUME ["/app"]

COPY . /app

RUN apk add --no-cache --virtual .build-deps build-base \
      && pip --no-cache-dir install -r requirements.txt \
      && apk del .build-deps

ENTRYPOINT ["python","payload_dumper.py"]
