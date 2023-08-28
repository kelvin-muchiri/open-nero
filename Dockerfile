# pull official base image
FROM python:3.9.1-alpine

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# create directory for the app user
RUN mkdir -p /home/app

# create the app user to make sure we do not run docker as root
# for security. If you are root in the container youl will be root in the host
RUN addgroup -S app && adduser -S app -G app

# create the appropriate directories
ENV HOME=/home/app
ENV APP_HOME=/home/app/web
RUN mkdir $APP_HOME
WORKDIR $APP_HOME

RUN apk update \
    # install psycopg2 dependencies
    && apk add postgresql-dev gcc python3-dev musl-dev \
    # install python-magic dependencies
    libmagic \
    # install paypalrestsdk dependencies
    libressl-dev libffi-dev \
    # install Pillow dependencies
    jpeg-dev zlib-dev libjpeg

COPY requirements/common.txt requirements/common.txt
COPY requirements/prod.txt requirements/prod.txt
# install dependencies
RUN pip install --upgrade pip
RUN pip install -r requirements/prod.txt --no-cache-dir

# copy project
COPY . $APP_HOME

# chown all the files to the app user
RUN chown -R app:app $APP_HOME

# change to the app user
USER app

EXPOSE 8000

CMD ["gunicorn", "--bind", ":8000", "--workers", "3", "nero.wsgi:application"]
