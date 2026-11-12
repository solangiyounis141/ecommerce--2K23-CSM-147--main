from fastapi import FastAPI

from .admin import router as admin_router
from .auth import router as auth_router
from .errors import register_error_handlers

app = FastAPI(title="Apparel Store API", version="0.2.0")
register_error_handlers(app)
app.include_router(auth_router)
app.include_router(admin_router)
