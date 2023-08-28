# Environment Variables

This document describes the environment variables in this code base and how to use them correctly to manuplate different sections.

Below is a list of currently supported environment variables:

- **DB_HOST**

  - Database host name
  - **Required**
  - default: None

- **DB_NAME**

  - Database name
  - **Required**
  - default: None

- **DB_USER**

  - Database user name
  - **Required**
  - default: None

- **DB_PORT**

  - Port to use to connect to the database
  - **Optional**
  - default: 5432

- **DB_PASSWORD**

  - Database password
  - **Required**
  - default: None

- **DEBUG**

  - [Boolean to turn on/off debug mode](https://docs.djangoproject.com/en/3.1/ref/settings/#debug)
  - **Optional**
  - default: False

- **SECRET_KEY**

  - [A secret key for a particular Django installation](https://docs.djangoproject.com/en/3.1/ref/settings/#secret-key)
  - **Required**
  - default: None

- **ALLOWED_HOSTS**

  - [A list of strings representing the host/domain names that this Django site can serve. This is a security measure to prevent HTTP Host header attacks, which are possible even under many seemingly-safe web server configurations](https://docs.djangoproject.com/en/3.1/ref/settings/#allowed-hosts)
  - **Optional**
  - default: []

- **DB_ENGINE**

  - The database backend to use.
  - **Required**
  - default: None

- **POSTGRES_PASSWORD**

  - This environment variable is normally required for you to use the PostgreSQL image. This environment variable sets the superuser password for PostgreSQL.
  - **Required**
  - default: None

- **POSTGRES_USER**

  - Used in conjunction with POSTGRES_PASSWORD to set a user and its password. This variable will create the specified user with superuser power and a database with the same name
  - **Optional**
  - default: None

- **POSTGRES_DB**

  - Define a different name for the default database that is created when the image is first started. If it is not specified, then the value of `POSTGRES_USER` will be used.
  - **Optional**
  - default: None

> Review the "Environment Variables" section of the [Postgres Docker Hub page](https://hub.docker.com/_/postgres) for more info on the postgres container environmental variables

If you do not provide `POSTGRES_USER` and `POSTGRES_DB`, you will have to login into the postgres container to create a database and a user that you can use for the project.

- **AWS_ACCESS_KEY_ID**

  - Amazon Web Services access key ID
  - **Required**
  - default: None

- **AWS_SECRET_ACCESS_KEY**

  - Amazon Web Services secret access key
  - **Required**
  - default: None

- **AWS_STORAGE_BUCKET_NAME**

  - Amazon Web Services storage bucket name
  - **Required**
  - default: None

- **CELERY_BROKER_URL**

  - Celery broker URL
  - **Required**
  - default: redis://redis:6379

- **MAIL_SERVER_URL**
  - The base URL of the server used to send emails. A sub domain is usually preferred just incase it is black listed, you can quickly set up another
  - default: http://web:8000/api/v1/
