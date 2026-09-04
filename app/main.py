from fastapi import FastAPI
from app.api import auth_routes, application_routes

app = FastAPI(title="Internship Tracker API")

app.include_router(auth_routes.router, prefix="/auth", tags=["auth"])
app.include_router(application_routes.router, prefix="/applications", tags=["applications"])