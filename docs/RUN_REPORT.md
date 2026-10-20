# Verified indexing run — 13 October 2026

Prepared **50,000 unique valid ArXiv papers**, with seed **42**, from **3,205,309** unique valid records in **3,205,432** source lines. The scan excluded 31 records with invalid original submission dates and 92 duplicate IDs. The raw 5,610,256,780-byte JSONL snapshot was streamed; duplicate tracking and sampling priorities were stored in a temporary disk-backed SQLite catalogue.

Strata use primary broad subject and five-year submission bands. Hamilton proportional quotas preserve the observed source distribution without assigning excessive weight to tiny strata. ID-based SHA256 priorities select within each stratum. Historical math/computer-science codes were assigned to their modern broad subjects before finalization. The independent full-size repeat produced identical JSONL, ID-map and SQLite checksums, source fingerprints and stratum counts.

| Broad subject | Unique valid source papers | Selected papers |
| --- | ---: | ---: |
| cs | 834,510 | 13,017 |
| econ | 12,981 | 203 |
| eess | 83,384 | 1,301 |
| math | 612,477 | 9,555 |
| other | 11 | 0 |
| physics | 1,546,778 | 24,129 |
| q-bio | 35,325 | 550 |
| q-fin | 13,763 | 215 |
| stat | 66,080 | 1,030 |

## Generated artifacts

The final corpus is in `data/processed/`: `papers.jsonl`, `papers.sqlite`, `doc_ids.json`, `manifest.json` and `reproducibility.json`. Indexes are in `data/indexes/`; model assets are in `data/models/`. All large generated artifacts are ignored by Git.

| Index | Shape | Representation |
| --- | --- | --- |
| TF-IDF | 50,000 × 129,591 | float32 CSR, 3,259,837 nonzero entries, unit rows |
| BM25 | 50,000 × 129,591 | int32 CSC postings, 3,259,837 term-frequency entries |
| Semantic / FAISS | 50,000 × 384 | float32 unit vectors, exact IndexFlatIP |

BM25 uses k1=1.5, b=0.75 and nonnegative Robertson IDF. TF-IDF uses smoothed IDF and sublinear term frequency. Both share Porter stemming and stopword removal. All rows use the same sorted ArXiv-ID mapping, including legacy IDs.

Semantic vectors use the official `sentence-transformers/all-MiniLM-L6-v2` snapshot, revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. Sentence Transformers retains tokenization, 256-token truncation, pooling and normalization. The remaining encoder work used a full-precision OpenVINO graph; 13,536 validated PyTorch vectors were reused by matching ID and semantic text. No weights were quantized. A local 32-document comparison found maximum normalized-vector difference 1.4249235e-7 between backends; regression tests also cover short and truncated long text. A single vector may represent only the truncated portion of a long abstract.

## Actual validation

**Passed for all 50,000 documents.** `data/indexes/validation.json` contains the checks and real retrieval examples. The verifier checked:

- Every corpus, index, original model and derived encoder artifact checksum.
- Unique sorted paper IDs and exact JSONL / SQLite / matrix / FAISS mappings.
- SQLite integrity and every stored metadata row.
- Every sample stratum count.
- Every lexical row re-tokenized from the corpus, with TF-IDF weights recomputed and smoothed IDF checked independently.
- BM25 document lengths, average length, document frequencies and IDF.
- Every embedding's finite values and unit norm, and every FAISS row reconstructed against the saved embedding.
- Five boundary/interior documents re-encoded with the original PyTorch model, plus FAISS self-match checks.
- Three real queries against each of TF-IDF, BM25 and semantic retrieval, including result mapping, unique results and score ordering.

Final regression run: **9 passed in 38.85 seconds; no skips**. Tests cover malformed/missing metadata, legacy IDs and categories, invalid dates, duplicate handling, sampling reproducibility including reordered input, quota allocation, scientific-token preservation, hand-calculated BM25 scores, actual small-model indexing, embedding reuse, encoder parity, lexical rankings/OOV queries and rejection of a corrupted ID mapping.

| Operation | Elapsed seconds | Peak resident memory (MiB) |
| --- | ---: | ---: |
| Corrected sample preparation | 637.689 | 160.8 |
| Independent repeat preparation | 429.160 | 170.5 |
| Final index build (with reuse) | 1544.349 | 1149.7 |
| Full index verification | 30.557 | 1020.1 |

These are measured local pipeline runs with shared CPU workloads. The final index-build time includes reuse; the earlier work that produced the reusable vectors is not included. These measurements do not measure relevance quality or query latency. Relevance evaluation requires relevance judgments.

## Integrity fingerprints

- Source SHA256: `9ee5aafa99209d6dbf4cd8c138dc662f290a7b49065d7301d4a0152bc0701c75`
- Final corpus JSONL SHA256: `82fc90aa637ec8d2580dcb89bc0bafc4202a5b6b061ae53b2ea4e6e26f049b9c`
- Shared ID-map SHA256: `4a529c272f5d9f96133fccf74f4c2c96c7fe353c37318aefccf05b172e445d83`

## Commands

Run from the repository root with the existing environment:

```powershell
.venv/Scripts/python.exe -m backend.pipeline.verify --expected-size 50000
.venv/Scripts/python.exe -m backend.pipeline.search "quantum field theory" --algorithm bm25
.venv/Scripts/python.exe -m backend.pipeline.search "galaxy formation" --algorithm semantic
.venv/Scripts/python.exe -m pytest backend/tests -q
```

[README](../README.md) contains fresh preparation/build commands and configuration options. Choose new output directories when reproducing alongside the finalized artifacts. This task implemented the offline preparation/indexing/verification pipeline and command-line retrievers; a web application and judged retrieval evaluation were outside this run.

Source files added: `backend/pipeline/dataset.py`, `text.py`, `indexes.py`, `download_model.py`, `cpu_model.py`, `checkpoint.py`, `search.py`, `verify.py`, `common.py`, package initializers and `backend/tests/test_pipeline.py`. Setup/documentation files added: `.gitignore`, `requirements.lock.txt`, `README.md` and this report. The raw snapshot was not modified.
