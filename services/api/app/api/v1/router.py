from fastapi import APIRouter

from app.api.v1.endpoints import alerts, auth, dashboard, predictions, readings, sites, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(sites.router)
api_router.include_router(readings.router)
api_router.include_router(alerts.router)
api_router.include_router(predictions.router)
api_router.include_router(predictions.model_router)
api_router.include_router(dashboard.router)
