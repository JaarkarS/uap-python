import os
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from .store import Store, Conflict, NotFound

class TaskIn(BaseModel):
    capability: str = Field(min_length=1)
    payload: dict = Field(default_factory=dict)
    max_attempts: int = Field(default=3, ge=1, le=100)
class ClaimIn(BaseModel):
    capability: str
    worker_id: str
    lease_seconds: int = Field(default=10, ge=2, le=3600)
class UpdateIn(BaseModel):
    lease_token: str
    lease_seconds: int = Field(default=10, ge=2, le=3600)
    value: object = None

def create_app(store=None):
    app=FastAPI(title='UAP Python Prototype',version='0.1.0')
    app.state.store=store or Store(os.getenv('UAP_DB','uap.db'))
    def auth(authorization):
        # API key is mandatory for every endpoint except health and spec metadata.
        expected=os.environ.get('UAP_API_KEY','dev-only-change-me')
        if authorization != 'Bearer '+expected: raise HTTPException(401,'Unauthorized')
    def act(fn,*args):
        try: return fn(*args)
        except NotFound: raise HTTPException(404,'Task not found')
        except Conflict as e: raise HTTPException(409,str(e))
    @app.get('/health')
    def health(): return {'status':'ok','protocol':'uap','version':'0.1'}
    @app.post('/uap/v1/tasks')
    def create(body:TaskIn, authorization:str|None=Header(None)):
        auth(authorization)
        return app.state.store.create(body.capability,body.payload,body.max_attempts)
    @app.get('/uap/v1/tasks/{tid}')
    def get(tid:str, authorization:str|None=Header(None)):
        auth(authorization)
        return act(app.state.store.get,tid)
    @app.post('/uap/v1/claim')
    def claim(body:ClaimIn,authorization:str|None=Header(None)):
        auth(authorization)
        return app.state.store.claim(body.capability,body.worker_id,body.lease_seconds)
    @app.post('/uap/v1/tasks/{tid}/{action}')
    def update(tid:str,action:str,body:UpdateIn,authorization:str|None=Header(None)):
        auth(authorization)
        if action not in ('heartbeat','checkpoint','complete','fail'):
            raise HTTPException(404,'Unknown operation')
        return act(app.state.store.mutate,tid,body.lease_token,action,body.value,body.lease_seconds)
    return app

app=create_app()
