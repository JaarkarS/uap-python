import json, urllib.request, urllib.error
class UAPClient:
    def __init__(self,url='http://127.0.0.1:8000',api_key='dev-only-change-me'):
        self.url=url.rstrip('/'); self.api_key=api_key
    def call(self,path,data=None):
        req=urllib.request.Request(self.url+path,data=None if data is None else json.dumps(data).encode(),headers={'Authorization':'Bearer '+self.api_key,'Content-Type':'application/json'},method='GET' if data is None else 'POST')
        try:
            with urllib.request.urlopen(req,timeout=30) as res: return json.loads(res.read())
        except urllib.error.HTTPError as e: raise RuntimeError(f'UAP HTTP {e.code}: {e.read().decode()}') from e
    def submit(self,capability,payload,max_attempts=3):
        return self.call('/uap/v1/tasks',{'capability':capability,'payload':payload,'max_attempts':max_attempts})
    def get(self,tid): return self.call('/uap/v1/tasks/'+tid)
    def claim(self,capability,worker_id,lease_seconds=10):
        return self.call('/uap/v1/claim',{'capability':capability,'worker_id':worker_id,'lease_seconds':lease_seconds})
    def update(self,tid,action,token,value=None,lease_seconds=10):
        return self.call(f'/uap/v1/tasks/{tid}/{action}',{'lease_token':token,'value':value,'lease_seconds':lease_seconds})
