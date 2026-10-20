"""Real-corpus HTTP contract smoke; creates unlabeled pools, never fabricates grades."""
import json
import time
from pathlib import Path
from fastapi.testclient import TestClient
from backend.api.config import Settings, ROOT
from backend.api.main import create_app


def wait(client,path):
    while True:
        response=client.get(path)
        response.raise_for_status()
        value=response.json()
        if value['status'] not in ('QUEUED','RUNNING'):
            return value
        time.sleep(.5)


def main():
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--benchmark',action='store_true')
    parser.add_argument('--iterations',type=int,default=3)
    args=parser.parse_args()
    settings=Settings(evaluation_mutations_enabled=True)
    with TestClient(create_app(settings)) as client:
        client.get('/api/v1/health/ready').raise_for_status()
        queries=client.get('/api/v1/evaluation/queries').json()
        response=client.post('/api/v1/evaluation/pools',json={'query_set_version':queries['version'],'depth':10})
        response.raise_for_status()
        pool=wait(client,'/api/v1/evaluation/pools/'+response.json()['id'])
        assert pool['status']=='COMPLETED',pool
        progress=client.get('/api/v1/evaluation/progress',params={'pool_id':pool['id']}).json()
        print(json.dumps(dict(pool=pool['id'],progress=progress)),flush=True)
        first=queries['queries'][0]['id']
        documents=client.get(f"/api/v1/evaluation/pools/{pool['id']}/judgments",params={'query_id':first,'limit':100})
        documents.raise_for_status()
        assert all('provenance' not in d for d in documents.json()['items'])
        no_labels=client.post('/api/v1/evaluation/runs',json={'pool_id':pool['id']})
        if progress['judged']==0:
            assert no_labels.status_code==409,no_labels.text
        report=dict(query_count=len(queries['queries']),pool=pool,progress=progress,
                    undeduplicated_max=len(queries['queries'])*40,
                    incomplete_run_status=no_labels.status_code,fixture_labels_written=0)
        if args.benchmark:
            response=client.post('/api/v1/evaluation/benchmarks',json={'query_set_version':queries['version'],
                'warmup_iterations':2,'measured_iterations':args.iterations,'depth':10})
            response.raise_for_status()
            benchmark=wait(client,'/api/v1/evaluation/benchmarks/'+response.json()['id'])
            report['benchmark']=benchmark
            print(json.dumps(dict(benchmark=benchmark['id'],status=benchmark['status'],summary=benchmark['summary'])),flush=True)
        for kind in ('queries','pool','judgments'):
            response=client.get('/api/v1/evaluation/export',params={'kind':kind,**({'id':pool['id']} if kind!='queries' else {})})
            response.raise_for_status()
        (ROOT/'docs/PHASE5_LIVE_SMOKE.json').write_text(json.dumps(report,indent=2),encoding='utf-8')


if __name__=='__main__':main()
