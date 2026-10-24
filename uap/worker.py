import argparse, os, socket, time
from .client import UAPClient

def run():
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker-id',default=socket.gethostname()+'-'+str(os.getpid()))
    parser.add_argument('--lease-seconds',type=int,default=10)
    parser.add_argument('--delay',type=float,default=0.1)
    args=parser.parse_args()
    client=UAPClient(os.getenv('UAP_URL','http://127.0.0.1:8000'),os.getenv('UAP_API_KEY','dev-only-change-me'))
    print('Worker',args.worker_id,'waiting for range.sum tasks',flush=True)
    while True:
        task=client.claim('range.sum',args.worker_id,args.lease_seconds)
        if task is None:
            time.sleep(0.5); continue
        tid=task['id']; token=task['lease_token']
        start=int(task['payload']['start']); end=int(task['payload']['end'])
        ck=task['checkpoint']
        pos=int(ck.get('next',start)); total=int(ck.get('sum',0))
        print('Task',tid,'attempt',task['attempts'],'resuming at',pos,flush=True)
        try:
            while pos<end:
                # Each checkpoint commits logical progress before the next chunk.
                stop=min(pos+100,end)
                total+=sum(range(pos,stop));pos=stop
                client.update(tid,'checkpoint',token,{'next':pos,'sum':total},args.lease_seconds)
                print('checkpoint',pos,flush=True)
                time.sleep(args.delay)
            client.update(tid,'complete',token,{'sum':total,'count':end-start})
            print('completed',tid,flush=True)
        except Exception as exc:
            print('Task interrupted:',exc,flush=True)
            try: client.update(tid,'fail',token,str(exc))
            except Exception: pass

if __name__=='__main__':run()
