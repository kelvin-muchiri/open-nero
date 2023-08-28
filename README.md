# Nero: A multi-tenant backend API for a freelance writing front-end application

This is the backend API service for a freelance writing front-end application. This project uses [django-tenant](https://django-tenants.readthedocs.io/en/latest/) to implement one schema per tenant type of [Multi-Tenant Data Architecure](https://docs.microsoft.com/en-us/azure/sql-database/saas-tenancy-app-design-patterns)

Can be hosted as a SaaS application offering per-tenant subscription. Tenant subscription billing is managed by [Paypal Subscriptions](https://developer.paypal.com/docs/subscriptions/)

## Getting Started

These instructions will get you a copy of the project up and running on your local machine for development and testing purposes.

### Prerequisites

Python >=3.9.1 installed on your machine. [Learn how to install multiple Python versions using Pyenv](https://realpython.com/intro-to-pyenv/)

An active python virtual environment. [Learn how to activate virtual environments using Pyenv](https://realpython.com/intro-to-pyenv/#virtual-environments-and-pyenv)

Docker and docker-compose installed.

### Development

#### Setting up the development environment

Change directory into the root of the project

Install the development requirements in your local virtual environment by executing in the terminal

```sh
pip install -r requirements/dev.txt
```

Install the pre-commit into the Git hooks folder (located under .git/hooks in the repo root) by executing in the terminal

```sh
pre-commit install
```

The pre-commit hooks will run for every future commit.

Create a `.env` file. Copy the contents of `.env_sample` into the newly created `.env`. Enter
the necessary values for the keys listed

Build a new image and spin up the containers

```sh
docker-compose up -d --build
```

After the containers are up, create the shared apps on the public schema by running

```sh
docker-compose exec web python manage.py migrate_schemas --shared
```

Now create your **public** schema and your **test** schema. Open the Django interactive shell

```sh
docker-compose exec web python manage.py shell
```

Create the public schema by running the following commands

```sh
from apps.tenants.models import *
tenant = Tenant(schema_name='public', name='Public')
tenant.save()
domain = Domain()
domain.domain = 'neromoto.com'
domain.tenant = tenant
domain.is_primary = True
domain.save()
```

Create the test tenant by running the following commands

```sh
from apps.tenants.models import *
tenant = Tenant(schema_name='test', name='Test')
tenant.save() # migrate_schemas automatically called, your tenant is ready to be used!
domain = Domain()
domain.domain = 'test.neromoto.com'
domain.tenant = tenant
domain.is_primary = True
domain.save()

# We also need to add another domain for our test schema that will be used locally when sending asynchronous emails with celery

domain = Domain()
domain.domain = 'web'
domain.tenant = tenant
domain.is_primary = False
domain.save()
```

Edit `/etc/hosts` file add add `neromoto.com test.neromoto.com`

```sh
127.0.0.1 localhost neromoto.com test.neromoto.com
```

Finally, we'll need to create our super user that will use to access the Django Admin interface. To create superuser a superuser for a schema named **test**

```sh
docker-compose exec web python manage.py tenant_command createsuperuser --schema=test
```

To visit Django Admin interface, visit <http://test.neromoto.com:8000/api/woza/> and login using
the credentials you above.

#### Other useful commands

To make migrations

```sh
docker-compose exec web python manage.py makemigrations
```

To migrate

```sh
docker-compose exec web python manage.py migrate
```

To create a new app

```sh
docker-compose exec web python manage.py startapp myapp
```

To run Django interactive shell on a schema named **test**

```sh
docker-compose exec web python manage.py tenant_command shell --schema=test
```

If an update to the pre-commit hooks is required run in terminal,

```sh
pre-commit autoupdate
```

### Package installation

To install a new package, update the corresponding `requirements/foo.txt` depending on the package's purpose.

For instance, if the package will be used by all environments, add it to `requirements/common.txt`, else if it will be used only in development e.g `coverage` add in `requirements/dev.txt`. Packages only available in the production environment will be added in `requirements/prod.txt`.

e.g To install `python-decouple` add it in `requirements/common.txt` as

```text
python-decouple==3.5
```

Run `pip install -r requirements/dev.txt` to install the package in your local environment.

Run `docker-compose up -d --build` to build a new image and spin up the containers.

To uninstall a package remove the package from the requirements file then run `docker-compose up -d --build` to build a new image and spin up the containers.

> **⚠ WARNING: Never run pip freeze into a requirements file**
> Using pip freeze to update a requirements file is not allowed as this will dump all packages regardless of enviroment

### Running tests

To run all tests

```sh
docker-compose exec web pytest -vv
```

To run tests on a specific module

```sh
docker-compose exec web pytest apps/users -vv
```

To run tests on a specific file

```sh
docker-compose exec web pytest apps/users/tests/test_views.py -vv
```

To run tests on a specific test case

```sh
docker-compose exec web pytest apps/users/tests/test_views.py::EmailVerificationEndTestCase -vv
```

### Deployment
