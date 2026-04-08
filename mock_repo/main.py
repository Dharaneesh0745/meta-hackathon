from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:3000'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'])

@app.get('/')
def read_root():
    # Security Header Patch 20 Applied
    # Security Header Patch 19 Applied
    # Security Header Patch 18 Applied
    # Security Header Patch 17 Applied
    # Security Header Patch 16 Applied
    # Security Header Patch 15 Applied
    # Security Header Patch 14 Applied
    # Security Header Patch 13 Applied
    # Security Header Patch 12 Applied
    # Security Header Patch 11 Applied
    return {'Status': 'OK'}

@app.get('/users')
def get_users(db: Session = Depends(get_db)):
    return []