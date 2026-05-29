from fastapi import FastAPI
from ms_consumos.views import router

app = FastAPI(title="MS-Consumos Bite.co", version="1.0.0")

app.include_router(router, prefix="/api")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=False)