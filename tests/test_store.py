import os, tempfile, time, unittest
from uap.store import Store,Conflict
class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.store=Store(os.path.join(self.tmp.name,'tasks.db'))
    def tearDown(self): self.tmp.cleanup()
    def test_complete_and_checkpoint(self):
        t=self.store.create('range.sum',{'start':0,'end':100})
        a=self.store.claim('range.sum','a',10)
        self.assertEqual(a['id'],t['id'])
        self.store.mutate(t['id'],a['lease_token'],'checkpoint',{'next':50,'sum':1225})
        final=self.store.mutate(t['id'],a['lease_token'],'complete',{'sum':4950})
        self.assertEqual(final['status'],'completed')
        with self.assertRaises(Conflict):self.store.mutate(t['id'],a['lease_token'],'heartbeat')
    def test_expired_lease_reclaimed_checkpoint_preserved(self):
        t=self.store.create('range.sum',{'start':0,'end':100},max_attempts=2)
        a=self.store.claim('range.sum','a',2)
        self.store.mutate(t['id'],a['lease_token'],'checkpoint',{'next':50,'sum':1225},2)
        with self.store.tx() as db:db.execute('UPDATE tasks SET lease_until=? WHERE id=?',(time.time()-1,t['id']))
        b=self.store.claim('range.sum','b',2)
        self.assertEqual(b['checkpoint']['next'],50)
        self.assertNotEqual(b['lease_token'],a['lease_token'])
        with self.assertRaises(Conflict):self.store.mutate(t['id'],a['lease_token'],'complete',{'sum':1})
        self.assertEqual(self.store.mutate(t['id'],b['lease_token'],'complete',{'sum':4950})['status'],'completed')
    def test_attempt_limit(self):
        t=self.store.create('x',{},max_attempts=1)
        self.store.claim('x','a',2)
        with self.store.tx() as db:db.execute('UPDATE tasks SET lease_until=? WHERE id=?',(time.time()-1,t['id']))
        self.assertIsNone(self.store.claim('x','b',2))
        self.assertEqual(self.store.get(t['id'])['status'],'failed')
if __name__=='__main__':unittest.main()
