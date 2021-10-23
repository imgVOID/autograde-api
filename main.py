from os.path import dirname, abspath
from fastapi import FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from routers import limiter
from routers.tasks import router_tasks
from routers.check import router_check
from routers.themes import router_themes
from routers.auth import router_users
from utilities.docker_scripts import DockerUtils
from utilities.app_metadata import tags_metadata, app_metadata_description
from database.config import database

# FastAPI app instance
app = FastAPI(title='Autograding-API',
              description=app_metadata_description,
              version='0.0.1',
              contact={
                  "name": "Maria Hladka",
                  "url": "https://github.com/imgVOID",
                  "email": "imgvoid@gmail.com",
              },
              license_info={
                  "name": "Apache 2.0",
                  "url": "https://www.apache.org/licenses/LICENSE-2.0.html",
              }, openapi_tags=tags_metadata)

# Save main app directory
APP_ROOT = dirname(abspath(__file__))
# Fix Docker dockerfile problems on the app startup
DockerUtils.fix_docker_bug()

# Connecting routers to the app
app.include_router(router_tasks)
app.include_router(router_check)
app.include_router(router_themes)
app.include_router(router_users)
# Connecting rate limiter to the app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.on_event("startup")
async def startup():
    await database.connect()


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()
