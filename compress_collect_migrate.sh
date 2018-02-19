#!/bin/sh
set -e

docker run --rm \
  --env ZAPPA=True \
  --env AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  --env AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  --env DB_USER=$DB_USER \
  --env DB_PASSWORD=$DB_PASSWORD \
  --env DB_HOST=$DB_HOST \
  --env DB_NAME=$DB_NAME \
  --env AWS_STORAGE_BUCKET_NAME_STATIC=$AWS_STORAGE_BUCKET_NAME_STATIC \
  --env AWS_STORAGE_BUCKET_NAME_MEDIA=$AWS_STORAGE_BUCKET_NAME_MEDIA \
  tesselo_zappa \
  python manage.py compress --force && \
  python manage.py collectstatic --noinput \
      -i tesselo \
      -i docs \
      -i fonts \
      -i *.md \
      -i *.txt \
      -i *.scss \
      -i *.less \
      -i *.json \
      -i *.hbs \
      -i *.html \
      -i package.json \
      -i bootswatch \
      -i LICENSE.md \
      -i LICENSE && \
    python manage.py migrate
