from fastapi import FastAPI
from app.routers.pmb import router as pmb_router
from app.routers.krs import router as krs_router

from app.routers.scheduling import router as scheduling_router

from app.routers.grades import router as grades_router

app = FastAPI(title="PMB, KRS, Jadwal, dan Nilai API", version="3.0.0")
app.include_router(pmb_router)
app.include_router(krs_router)
app.include_router(scheduling_router)
app.include_router(grades_router)

@app.get("/")
def root():
    return {"message": "PMB API aktif"}
