# app/apis/v1/tracking/router.py
from fastapi import APIRouter
from app.apis.v1.tracking import location_history, cities, people

router = APIRouter()
router.include_router(location_history.router)
router.include_router(cities.router)
router.include_router(people.router)