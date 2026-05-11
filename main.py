# main.py
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routes.auth_routes import auth_router
from routes.database_routes import db_router
from routes.backup_routes import backup_router
from routes.settings_routes import settings_router
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(
    root_path="/dumpty",
    title="Dumpty API",
    version="1.0.0",
    contact={
        "name": "Anshul Badoni",
        "email": "anshul.badoni@ashmar.in"
    }
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(db_router)  
app.include_router(backup_router)
app.include_router(settings_router)

@app.get("/")
def read_root():
    return {"Hello": "World"}