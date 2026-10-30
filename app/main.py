from fastapi import FastAPI
from app.api import auth_routes, application_routes, parsed_applications_routes,analytics_routes

app = FastAPI(title="Internship Tracker API")

app.include_router(auth_routes.router, prefix="/auth", tags=["auth"])
app.include_router(application_routes.router, prefix="/applications", tags=["applications"])
app.include_router(parsed_applications_routes.router , tags=["parsed_applications"])
app.include_router(analytics_routes.router)