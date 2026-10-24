import json, os, sqlite3, time, uuid
from contextlib import contextmanager

class Conflict(Exception): pass
class NotFound(Exception): pass

class Store:
    def __init__(self, path='uap.db'):
        self.path = path
        self.init()

    @contextmanager
    def tx(self):
        con = sqlite3.connect(self.path, timeout=15, isolation_level=None)
        con.row_factory = sqlite3.Row
        try:
            con.execute('BEGIN IMMEDIATE')
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally: con.close()

    def init(self):
        with self.tx() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS tasks (
              id TEXT PRIMARY KEY, capability TEXT NOT NULL, payload TEXT NOT NULL,
              status TEXT NOT NULL, checkpoint TEXT NOT NULL DEFAULT '{}',
              result TEXT, error TEXT, worker_id TEXT, lease_token TEXT,
              lease_until REAL, attempts INTEGER NOT NULL DEFAULT 0,
              max_attempts INTEGER NOT NULL DEFAULT 3,
              created_at REAL NOT NULL, updated_at REAL NOT NULL)''')
            db.execute('CREATE INDEX IF NOT EXISTS task_claim_idx ON tasks(status,capability,lease_until)')

    @staticmethod
    def decode(row):
        if not row: return None
        x = dict(row)
        for field in ('payload','checkpoint','result'):
            if x[field] is not None: x[field] = json.loads(x[field])
        return x

    def create(self, capability, payload, max_attempts=3):
        tid = str(uuid.uuid4()); now = time.time()
        with self.tx() as db:
            db.execute('INSERT INTO tasks(id,capability,payload,status,max_attempts,created_at,updated_at) VALUES(?,?,?,?,?,?,?)',
                       (tid,capability,json.dumps(payload),'queued',max_attempts,now,now))
        return self.get(tid)

    def get(self, tid):
        with self.tx() as db:
            row = db.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
        if row is None: raise NotFound(tid)
        return self.decode(row)

    def claim(self, capability, worker_id, lease_seconds=10):
        now = time.time()
        with self.tx() as db:
            # Expired jobs remain claimable; exhausted jobs are terminal.
            db.execute("UPDATE tasks SET status='failed', error='lease expired; retry limit reached',worker_id=NULL,lease_token=NULL,lease_until=NULL,updated_at=? WHERE status='running' AND lease_until<=? AND attempts>=max_attempts",(now,now))
            row = db.execute('''SELECT * FROM tasks WHERE capability=? AND attempts<max_attempts AND
                (status='queued' OR (status='running' AND lease_until<=?))
                ORDER BY created_at,id LIMIT 1''',(capability,now)).fetchone()
            if not row: return None
            token = str(uuid.uuid4())
            db.execute('''UPDATE tasks SET status='running',worker_id=?,lease_token=?,lease_until=?, attempts=attempts+1,updated_at=? WHERE id=?''',
                (worker_id,token,now+lease_seconds,now,row['id']))
            return self.decode(db.execute('SELECT * FROM tasks WHERE id=?',(row['id'],)).fetchone())

    def mutate(self, tid, token, action, value=None, lease_seconds=10):
        now=time.time()
        with self.tx() as db:
            row=db.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone()
            if not row: raise NotFound(tid)
            if row['status']!='running' or row['lease_token']!=token or row['lease_until']<=now:
                raise Conflict('Lease is missing, expired, or owned by another worker')
            if action=='heartbeat':
                db.execute('UPDATE tasks SET lease_until=?,updated_at=? WHERE id=?',(now+lease_seconds,now,tid))
            elif action=='checkpoint':
                db.execute('UPDATE tasks SET checkpoint=?,lease_until=?,updated_at=? WHERE id=?',(json.dumps(value),now+lease_seconds,now,tid))
            elif action=='complete':
                db.execute("UPDATE tasks SET status='completed',result=?,lease_token=NULL,lease_until=NULL,updated_at=? WHERE id=?",(json.dumps(value),now,tid))
            elif action=='fail':
                status='failed' if row['attempts']>=row['max_attempts'] else 'queued'
                db.execute('UPDATE tasks SET status=?,error=?,lease_token=NULL,lease_until=NULL,worker_id=NULL,updated_at=? WHERE id=?',(status,str(value),now,tid))
            else: raise ValueError(action)
            return self.decode(db.execute('SELECT * FROM tasks WHERE id=?',(tid,)).fetchone())
