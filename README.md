# Docker-based setup


### 🔧 Project Setup Summary (Dockerized Django App)

This project is a Dockerized Django web application with support for both **development** and **production** environments. It uses `docker-compose` and its **override mechanism** to adapt the setup depending on the deployment context.

* The **base configuration** is defined in `docker-compose.yml`, while **development-specific overrides** (e.g., code mounting, live reload) are in `docker-compose.override.yml`.
* A single `Dockerfile` is used to build a Python environment for the app, installing dependencies and preparing the Django app.
* The system defines **three services**: the Django **web** app (using Gunicorn), a **PostgreSQL database**, and an **Nginx reverse proxy** to serve static files.
* A single entrypoint file is used (`entrypoint.sh`) to handle the startup routines depending on the environment (variable `IS_DEVELOPMENT_ENV` used), including static files collection, DB migrations, and background job scheduling.
* In the python part, also a `.env.dev` and `.env.prod` files are used to read the environment variables in every scenario.

You can run:

* **Development mode** with `docker-compose up --build` (hot reload, local code mounted)
* **Production mode** with `docker-compose -f docker-compose.yml up --build -d` (fully isolated and optimized container)

---

Vols que ho tradueixi al català o castellà si ho prefereixes en un altre idioma?


### 📁 Project Structure (Relevant Parts)

```
biz-app/xliff_project/
│
├── app/                                 # Django app(s)
├── aitranslator_batch_process/          # Scheduled batch jobs
├── xliff_project/                       # Django settings and WSGI entry
├── manage.py
├── Dockerfile                           # Docker build instructions
├── docker-compose.yml                   # Main production configuration
├── docker-compose.override.yml          # Development-only overrides
├── entrypoint.sh                    # Development entrypoint script
├── .env.prod                            # Environment variables for production
├── .env.dev                             # Environment variables for development
├── requirements.txt
```

## Very important!! 
We are using docker-compose overriding mechanism, meaning:
- When executing `docker-compose up --build`this will read the `docker-compose.yml`and also `docker.compose.override.yml` overriding the former.
- To build the images for PROD we need to run `docker-compose -f docker-compose.yml up --build -d` and the overriding file will be avoided.

Also, we are using a variable`IS_DEVELOPMENT_ENV`that is used in all docker files to route to the right files.

## 🧱 How the Build Works for PRODuction 

### 📦 Dockerfile 

The Dockerfile defines a Python container that installs dependencies, collects static files, applies migrations, and starts the app using Gunicorn.
- For PROD we use 🧩 `docker-compose.yml` 

3 services are defined:

* **web**: Django application (with Gunicorn for Python interpreter)
* **db**: PostgreSQL database 
* **frontend-proxy**: Nginx for serving static files and proxying to Django

### 🛠 Entrypoint

The `entrypoint.prod.sh` used in production executes:

1. A background scheduler for batch jobs
2. `collectstatic`to collect all static files
3. `migrate`the changes on the database and checks consistency
4. Starts the app with Gunicorn (with 3 workers for maximum performance and no reload)


## 🧱 How the Build Works for DEVelopment

### 📦 Dockerfiles 

The Dockerfile defines a Python container that installs dependencies, collects static files, applies migrations, and starts the app using Gunicorn.

- For DEV we use 🧩 `docker-compose.yml` + `docker-compose.override.yml` 

In any scenario, 3 services are defined:

* **web**: Django application (with Gunicorn for Python interpreter)
* **db**: PostgreSQL database 
* **frontend-proxy**: Nginx for serving static files and proxying to Django

The `docker-compose.override.yml`overrides the base Compose file to:

* Mount the local code folder into the container (`.:/app`) --> this allows to share the code between local and the container and avoid rebuilding the image for every change in the code
* Swap the production entrypoint with `entrypoint.dev.sh`

### 🛠 Entrypoint

The `entrypoint.sh` is driven by the environment in which is executed:

1. A background scheduler for batch jobs
2. `collectstatic`to collect all static files
3. `migrate`the changes on the database and checks consistency
4. Starts Gunicorn with 1 thread and the `--reload` option to allow hot reloading while developing


## ▶️ How to RUN for PRODuction 

Run:

   ```bash
   docker-compose -f docker-compose.yml up --build -d

   # (-d is for detach) 
   # This command will avoid not picking up the docker-compose-override.yml file
   ```

   * Hot-reloads on file changes
   * Runs with code bind-mounted from host
   * Uses `.env.prod` if needed (just reference it in Compose)


## ▶️ How to RUN for DEVelopment

Run:

   ```bash
   docker-compose up --build -d

   # (-d option is for detach)
   # file docker-compose.override.yml will be taken an override the docker-compose.yml settings
   ```

2. This:

   * Builds the image from scratch
   * Runs migrations, collects static files
   * Launches Gunicorn on development mode
   * Uses `.env.dev`

3. Optional cleanup before deploy:

   ```bash
   docker-compose down --volumes --remove-orphans
   docker system prune -af
   ```