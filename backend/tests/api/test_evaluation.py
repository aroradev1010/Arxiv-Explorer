"""Deterministic test corpus only. Grades here are fixtures, never production judgments."""
import json
import math
import sqlite3
import time
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.api.main import create_app
from backend.api.services import SearchService
from backend.api.errors import APIError
from backend.evaluation.metrics import evaluate, aggregate, latency_summary
from backend.evaluation.service import EvaluationService, MODES
from backend.evaluation.schemas import QueryCollection, PoolRequest, Judgment, RunRequest, BenchmarkRequest
from backend.evaluation.store import Store


QUERY = dict(id='Q001',query='quantum',information_need='Find quantum field research.',domain='physics',query_type='exact',notes='Test fixture only')


@pytest.fixture
def evaluation(resources,tmp_path):
    settings = resources.settings.model_copy(update={'evaluation_enabled':True,'evaluation_mutations_enabled':True,
                                                    'evaluation_db_path':tmp_path/'evaluation.sqlite'})
    return EvaluationService(settings,SearchService(resources))


def pool_for(evaluation,depth=10):
    version = evaluation.save_queries([QUERY])['version']
    pool_id, fresh = evaluation.reserve_pool(PoolRequest(query_set_version=version,depth=depth))
    if fresh:
        evaluation.generate_pool(pool_id)
    assert evaluation.pool(pool_id)['status']=='COMPLETED'
    return pool_id


def test_hand_calculated_formulas():
    judgments={'a':2,'b':0,'c':1,'d':2,'outside':1}
    m=evaluate(['a','b','c','d'],judgments,10)
    assert m['precision']==.3
    assert m['pooled_recall']==.75
    assert m['ap']==pytest.approx((1+2/3+3/4)/4)
    dcg=3+1/2+3/math.log2(5)
    ideal=3+3/math.log2(3)+1/2+1/math.log2(5)
    assert m['dcg']==pytest.approx(dcg)
    assert m['ndcg']==pytest.approx(dcg/ideal)
    assert m['curves'][2]==dict(rank=3,precision=2/3,pooled_recall=.5)
    strict=evaluate(['a','b','c','d'],judgments,10,2)
    assert strict['precision']==.2
    assert strict['pooled_recall']==1
    assert strict['ap']==pytest.approx((1+2/4)/2)
    assert strict['ndcg']==m['ndcg']
    assert aggregate([m,strict])['ap']==pytest.approx((m['ap']+strict['ap'])/2)


def test_unknown_zero_cutoff_and_duplicate_policies():
    m=evaluate(['a','b'],{'a':2},10)
    assert m['coverage']==.5 and m['precision'] is None and m['curves']==[]
    zero=evaluate(['a'],{'a':0},10)
    assert zero['precision']==0 and zero['ap'] is None and zero['pooled_recall'] is None
    assert zero['ndcg'] is None and zero['status']=='NO_KNOWN_RELEVANT'
    assert evaluate(['a'],{'a':2},10)['precision']==.1
    assert evaluate([],{},10)['precision']==0
    with pytest.raises(ValueError): evaluate(['a','a'],{'a':1})
    with pytest.raises(ValueError): evaluate([],{},0)
    with pytest.raises(ValueError): evaluate(['a'],{'a':4})
    assert aggregate([zero])['ap_query_count']==0


def test_latency_arithmetic():
    s=latency_summary([1,2,3,4,5])
    assert s['mean']==3 and s['p50']==3
    assert s['p95']==pytest.approx(4.8)
    assert s['stddev']==pytest.approx(math.sqrt(2))
    assert latency_summary([])['mean'] is None
    assert latency_summary([9])['p95']==9


def test_query_versioning_and_validation(evaluation):
    assert len(evaluation.queries()['queries'])==30
    first=evaluation.save_queries([QUERY])
    assert first['version']==evaluation.save_queries([QUERY])['version']
    changed=evaluation.save_queries([{**QUERY,'query':'quantum field'}])
    assert first['version']!=changed['version']
    assert evaluation.queries(first['version'])['queries'][0]['query']=='quantum'
    with pytest.raises(ValidationError):QueryCollection(queries=[QUERY,QUERY])
    with pytest.raises(ValidationError):PoolRequest(query_ids=['Q001','Q001'])


def test_frozen_pool_dedup_provenance_order(evaluation):
    pool_id=pool_for(evaluation)
    docs=evaluation.documents(pool_id)
    assert len(docs)==len({r['paper_id'] for r in docs})
    assert set(m for r in docs for m in json.loads(r['provenance']))==set(MODES)
    assert all(p['rank']<=10 for r in docs for p in json.loads(r['provenance']).values())
    assert sorted(r['annotation_order'] for r in docs)==list(range(len(docs)))
    assert pool_for(evaluation)==pool_id
    version=evaluation.pool(pool_id)['metadata']['query_set_version']
    other,_=evaluation.reserve_pool(PoolRequest(query_set_version=version,random_seed=43))
    evaluation.generate_pool(other)
    assert len(evaluation.documents(other))==len(docs)
    assert [r['paper_id'] for r in evaluation.documents(other)]!=[r['paper_id'] for r in docs]
    new,_=evaluation.reserve_pool(PoolRequest(query_set_version=version,depth=12))
    assert new!=pool_id
    assert evaluation.pool(pool_id)['metadata']['depth']==10
    blind=evaluation.judgments(pool_id,'Q001',0,100,'all','')
    assert all('provenance' not in r and 'rank' not in r and 'score' not in r for r in blind['items'])


def test_judgments_readiness_persistence_and_snapshot(evaluation):
    pool_id=pool_for(evaluation)
    documents=evaluation.documents(pool_id)
    assert evaluation.readiness(pool_id)['missing_required']==len(documents)
    with pytest.raises(APIError,match='No query'):evaluation.run(RunRequest(pool_id=pool_id))
    first=documents[0]['paper_id']
    for grade in (0,1,2,None):
        evaluation.judge(pool_id,Judgment(query_id='Q001',paper_id=first,relevance_grade=grade))
        assert evaluation.documents(pool_id)[0]['relevance_grade']==grade
    for i,r in enumerate(documents):
        evaluation.judge(pool_id,Judgment(query_id='Q001',paper_id=r['paper_id'],relevance_grade=i%3))
    assert evaluation.readiness(pool_id)['eligible_queries']==1
    run=evaluation.run(RunRequest(pool_id=pool_id))
    assert len(run['metrics'])==4
    snapshot=run['judgment_snapshot']
    evaluation.judge(pool_id,Judgment(query_id='Q001',paper_id=first,relevance_grade=None))
    assert evaluation.get_run(run['id'])['judgment_snapshot']==snapshot
    restarted=EvaluationService(evaluation.settings,evaluation.search)
    assert restarted.get_run(run['id'])['metrics']==run['metrics']
    assert restarted.readiness(pool_id)['missing_required']==1
    for query,paper in [('Q_BAD',first),('Q001','unknown')]:
        with pytest.raises(APIError):evaluation.judge(pool_id,Judgment(query_id=query,paper_id=paper,relevance_grade=2))
    assert evaluation.readiness(pool_id)['judged']==len(documents)-1


def test_stale_and_shallow(evaluation):
    pool_id=pool_for(evaluation,5)
    assert evaluation.readiness(pool_id)['queries'][0]['status']=='INSUFFICIENT_DEPTH'
    with pytest.raises(APIError):evaluation.run(RunRequest(pool_id=pool_id))
    evaluation.search.resources.index_version='changed'
    assert evaluation.pool(pool_id)['stale']
    with pytest.raises(APIError):evaluation.judge(pool_id,Judgment(query_id='Q001',paper_id=evaluation.documents(pool_id)[0]['paper_id'],relevance_grade=1))


def test_empty_retrieval_and_failed_pool(evaluation,monkeypatch):
    monkeypatch.setattr(evaluation.search,'rankings',lambda *args:({m:[] for m in MODES},None,None))
    pool_id=pool_for(evaluation)
    assert evaluation.pool(pool_id)['candidate_count']==0
    assert evaluation.run(RunRequest(pool_id=pool_id))['metrics'][0]['precision']==0
    def fail(*args):raise RuntimeError('fixture retrieval failure')
    monkeypatch.setattr(evaluation.search,'rankings',fail)
    failed,_=evaluation.reserve_pool(PoolRequest(depth=5))
    evaluation.generate_pool(failed)
    assert evaluation.pool(failed)['status']=='FAILED'
    assert evaluation.documents(failed)==[]


def test_foreign_keys_and_rollback(evaluation):
    with pytest.raises(sqlite3.IntegrityError):
        with evaluation.store.connection() as db:
            db.execute("INSERT INTO relevance_judgments VALUES ('bad','Q001','paper',2,'human','now','now')")
    assert evaluation.store.rows('SELECT * FROM relevance_judgments')==[]


def test_benchmark_samples_warmup_and_errors(evaluation,monkeypatch):
    version=evaluation.save_queries([QUERY])['version']
    request=BenchmarkRequest(query_set_version=version,warmup_iterations=1,measured_iterations=2)
    job=evaluation.reserve_benchmark(request)
    evaluation.benchmark(job)
    result=evaluation.get_benchmark(job)
    assert result['status']=='COMPLETED'
    assert len(result['samples'])==12
    assert all(v['count']==2 for v in result['summary'].values())
    assert all(s['timing_breakdown'] for s in result['samples'])
    def fail(*args):raise RuntimeError('failed fixture search')
    monkeypatch.setattr(evaluation.search,'search',fail)
    job=evaluation.reserve_benchmark(request)
    evaluation.benchmark(job)
    failed=evaluation.get_benchmark(job)
    assert failed['status']=='COMPLETED_WITH_ERRORS' and failed['failed_samples']==12
    assert all(v['count']==0 and v['mean'] is None for v in failed['summary'].values())


def wait_job(client,path):
    for _ in range(250):
        response=client.get(path)
        assert response.status_code==200,response.text
        if response.json()['status'] not in ('RUNNING','QUEUED'):return response.json()
        time.sleep(.02)
    pytest.fail('Fixture job did not finish')


def test_evaluation_api_end_to_end(evaluation,resources):
    with TestClient(create_app(evaluation.settings,lambda _:resources)) as client:
        base='/api/v1/evaluation'
        collection=client.post(base+'/queries',json={'queries':[QUERY]}).json()
        assert client.get(base+'/queries').json()['version']==collection['version']
        edited=client.patch(base+'/queries/Q001',json={**QUERY,'notes':'reviewed test fixture'})
        assert edited.status_code==200 and edited.json()['version']!=collection['version']
        response=client.post(base+'/pools',json={'query_set_version':collection['version']})
        assert response.status_code==202,response.text
        pool_id=response.json()['id']
        assert wait_job(client,base+'/pools/'+pool_id)['status']=='COMPLETED'
        assert client.post(base+'/pools',json={'query_set_version':collection['version']}).json()['id']==pool_id
        documents=client.get(base+f'/pools/{pool_id}/judgments',params={'query_id':'Q001','limit':100}).json()['items']
        assert client.post(base+'/runs',json={'pool_id':pool_id}).status_code==409
        for p in documents:
            assert client.put(base+f'/pools/{pool_id}/judgments',json={'query_id':'Q001','paper_id':p['paper_id'],'relevance_grade':2}).status_code==200
        assert client.get(base+'/progress',params={'pool_id':pool_id}).json()['missing_required']==0
        response=client.post(base+'/runs',json={'pool_id':pool_id})
        assert response.status_code==201,response.text
        run=response.json()
        assert all(m['precision']==1 for m in run['metrics'])
        assert client.get(base+f"/runs/{run['id']}/metrics").status_code==200
        assert client.get(base+f"/runs/{run['id']}/queries").status_code==200
        assert len(client.get(base+f"/runs/{run['id']}/curves").json()['points'])==40
        for kind in ['run','metrics','aggregate','curves','report']:
            assert client.get(base+'/export',params={'kind':kind,'id':run['id'],'format':'md' if kind=='report' else 'csv'}).status_code==200
        bench=client.post(base+'/benchmarks',json={'query_set_version':collection['version'],'warmup_iterations':0,'measured_iterations':1}).json()
        assert wait_job(client,base+'/benchmarks/'+bench['id'])['completed_samples']==4
        assert client.get(base+'/benchmarks').status_code==200
        assert client.get(base+'/export',params={'kind':'benchmark','id':bench['id']}).status_code==200
        assert client.put(base+f'/pools/{pool_id}/judgments',json={'query_id':'Q001','paper_id':'unknown','relevance_grade':3}).status_code==422
        assert client.post(base+'/pools',json={'depth':101}).status_code==422
        assert client.get(base+'/runs/bogus').status_code==404


def test_mutation_security(evaluation,resources):
    settings=evaluation.settings.model_copy(update={'evaluation_mutations_enabled':False})
    with TestClient(create_app(settings,lambda _:resources)) as c:
        assert c.get('/api/v1/evaluation/queries').status_code==200
        assert c.post('/api/v1/evaluation/queries',json={'queries':[QUERY]}).status_code==403
    with TestClient(create_app(evaluation.settings,lambda _:resources)) as c:
        assert c.post('/api/v1/evaluation/queries',json={'queries':[QUERY]},headers={'Origin':'https://untrusted.example'}).status_code==403
    settings=evaluation.settings.model_copy(update={'app_env':'production'})
    with TestClient(create_app(settings,lambda _:resources)) as c:
        assert c.post('/api/v1/evaluation/benchmarks',json={}).status_code==403


def test_job_admission(evaluation,resources,monkeypatch):
    with TestClient(create_app(evaluation.settings,lambda _:resources)) as c:
        s=c.app.state.evaluation
        s.job_lock.acquire()
        try:
            assert c.post('/api/v1/evaluation/benchmarks',json={}).status_code==409
            assert c.post('/api/v1/evaluation/pools',json={}).status_code==409
        finally:s.job_lock.release()


def test_status_report_before_judgments(evaluation,resources):
    with TestClient(create_app(evaluation.settings,lambda _:resources)) as c:
        response=c.get('/api/v1/evaluation/export',params={'kind':'report','format':'md'})
        assert response.status_code==200
        assert 'No effectiveness conclusions' in response.text
        assert 'ground truth' not in response.text


def test_same_query_set_exclusions_and_extended_pool(evaluation):
    second={**QUERY,'id':'Q002','query':'field'}
    version=evaluation.save_queries([QUERY,second])['version']
    pool_id,_=evaluation.reserve_pool(PoolRequest(query_set_version=version,depth=12))
    evaluation.generate_pool(pool_id)
    docs=evaluation.documents(pool_id)
    for r in docs:
        if r['query_id']=='Q001' and any(p['rank']<=10 for p in json.loads(r['provenance']).values()):
            evaluation.judge(pool_id,Judgment(query_id='Q001',paper_id=r['paper_id'],relevance_grade=0))
    run=evaluation.run(RunRequest(pool_id=pool_id))
    assert run['metadata']['eligible_queries']==['Q001']
    assert run['metadata']['excluded_queries'][0]['query_id']=='Q002'
    assert all(m['precision']==0 and m['ap'] is None for m in run['metrics'])
    assert all(a['query_count']==1 and a['ap_query_count']==0 for a in run['metadata']['aggregate'].values())


def test_restart_marks_interrupted_jobs_failed(evaluation):
    pool_id,_=evaluation.reserve_pool(PoolRequest())
    assert evaluation.pool(pool_id)['status']=='QUEUED'
    Store(evaluation.settings.evaluation_db_path)
    assert evaluation.pool(pool_id)['status']=='FAILED'
