# app/apis/v1/router.py
from fastapi import APIRouter

from app.apis.v1 import auth, audit, map, provinces, services, users, population
from app.apis.v1.tracking   import tracking_router
from app.apis.v1.traffic    import nou
from app.apis.v1.poi import agg

router = APIRouter()

router.include_router(auth.router)
router.include_router(users.router)
router.include_router(provinces.router)
router.include_router(services.router)
router.include_router(map.router)
router.include_router(audit.router)
router.include_router(population.router)  
router.include_router(tracking_router)
router.include_router(nou.router)
router.include_router(agg.router)