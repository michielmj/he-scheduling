import uvicorn
from fastapi import FastAPI
from he_scheduling.core.version import get_version
from he_scheduling.api.v1.master_planning import router as master_planning

app = FastAPI(
    title="HE Scheduling API",
    description="This is the HE Scheduling micro-service.",
    version=get_version(),
)

app.include_router(router=master_planning)


@app.get("/")
def read_root():
    """
    Root endpoint providing basic information about the API, including
    the project name, version, description, and useful endpoints.
    """
    return {
        "project_name": app.title,
        "version": app.version,
        "description": app.description,
        "endpoints": {
            "root": "/",
            # "users": "/users/",
            # "items": "/items/",
            "docs": "/docs",  # Swagger UI documentation
            "redoc": "/redoc",  # ReDoc documentation
        },
        "message": "Welcome to the API! Visit /docs for the interactive API documentation.",
    }


def run():
    uvicorn.run("he_scheduling.main:app", host="0.0.0.0", port=8000)
