# Repeated latency benchmarking

Benchmarks are an explicit local action. They do not measure relevance and do not start on dashboard load. Loaded indexes and the embedding model are reused; no downloads, reindexing, or corpus embedding generation occurs.

Default: 2 warmup rounds and 10 measured rounds for each query/method pair. All warmups finish before measured rounds. Query/method execution order is shuffled deterministically per round using the saved seed. One background retrieval job is admitted at a time. Pool generation and benchmarking share that admission slot. Ordinary search remains available; for defensible timing, avoid using it during a benchmark and avoid builds/tests/indexing/unrelated heavy tasks.

Each sample records query, mode, iteration, warmup flag, UTC timestamp, total wall time in milliseconds, stage timings (preprocessing, eligibility, embedding, retrieval, fusion, metadata), and an error on failure. The scope is the full `SearchService.search` call, excluding HTTP transport, executor queue time, model load, and database sample persistence. HTTP round-trip and cold startup measurements are not implemented as benchmark modes; startup_ms remains available in existing system stats.

Summaries exclude warmup and failed samples. They contain mean, P50 (median), P95, min, max, population standard deviation, and successful measured count. P95 uses linear interpolation at `(N-1)*.95`; [1,2,3,4,5] yields P95=4.8. Errors have null latency and cannot become zero-ms successes. Partial failures yield COMPLETED_WITH_ERRORS and counts remain visible; fatal job failures yield FAILED. Process interruption marks incomplete jobs FAILED on restart. Warmup samples remain exportable.

Saved environment metadata includes actual OS, Python version, CPU text where available (otherwise null), logical CPU count, worker/computation threads, model name, corpus size, index/configuration versions, and measurement scope. This is observational local-machine timing, not a guarantee for other hardware or HTTP deployment latency. The application cannot detect all unrelated background load; record experimental conditions when using these numbers in a report.

```powershell
$env:EVALUATION_MUTATIONS_ENABLED='true'
.venv/Scripts/python.exe -m backend.api
# In another PowerShell terminal:
$base='http://127.0.0.1:8000/api/v1/evaluation'
$body=@{warmup_iterations=2; measured_iterations=10; depth=10; random_seed=42} | ConvertTo-Json
$job=Invoke-RestMethod "$base/benchmarks" -Method Post -ContentType 'application/json' -Body $body
Invoke-RestMethod "$base/benchmarks/$($job.id)"
Invoke-WebRequest "$base/export?kind=benchmark&id=$($job.id)&format=csv" -OutFile 'var/benchmark-samples.csv'
```

Use the dashboard to poll progress and inspect P50/P95, mean and spread. Benchmark exports include raw successful/failed samples and warmup flags for independent auditing.
