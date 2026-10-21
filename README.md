# ArXiv Explorer

## Project Overview

ArXiv Explorer is an academic research paper search engine for a collection of 50,000 arXiv papers. It provides a web interface for searching papers, applying filters, finding related papers and comparing retrieval methods.

## Features

- TF-IDF and BM25 keyword search.
- Semantic search using Sentence Transformers and FAISS.
- Hybrid search using Reciprocal Rank Fusion (RRF).
- Category, subject, author and publication-year filters.
- Paper details, arXiv links and paper recommendations.
- Algorithm comparison and evaluation with precision–recall curves.

## Tech Stack

- **Frontend:** Next.js, React, TypeScript and Tailwind CSS.
- **Backend:** Python and FastAPI.
- **Database:** SQLite.
- **Retrieval:** scikit-learn, NLTK, NumPy, SciPy, Sentence Transformers, PyTorch and FAISS.

## Project Structure

```text
backend/
  api/          API routes, metadata access and retrieval methods
  pipeline/     Offline dataset and index preparation
  evaluation/   CSV validation and evaluation metrics
frontend/
  app/          Application pages
  components/   Interface components
  lib/          API client, URL state and evaluation reader
data/
  processed/    Paper corpus, SQLite database and paper IDs
  indexes/      Search indexes and embeddings
  models/       Local Sentence Transformer assets
  evaluation/   Relevance grades, saved rankings and results
var/            Application metadata database
```

## Installation and Setup

### Prerequisites

Install **Python 3.12** with the Windows `py` launcher and **Node.js 22.12 or later in the 22.x series**, including npm. Run the following commands in PowerShell from the project root, the folder containing this README.

### Install dependencies

```powershell
py -3.12 -m venv .venv
$env:VIRTUAL_ENV = (Resolve-Path .venv).Path
$env:Path = "$env:VIRTUAL_ENV\Scripts;$env:Path"
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
cd frontend
npm ci
cd ..
```

The two environment assignments activate `.venv` for the current terminal without requiring an activation script.

No API keys are required. The default settings work locally; `.env.example` lists the backend configuration options. Keep an existing `.env` when already configured.

### Required assets

Large runtime assets are excluded from Git. A cloned repository alone cannot serve searches. Obtain the matching project asset bundle and place its files at these locations:

| Location | Required contents |
| --- | --- |
| `data/processed/` | Paper corpus, `papers.sqlite`, paper-ID mapping and manifest |
| `data/indexes/` | TF-IDF and BM25 files, `embeddings.npy`, `semantic.faiss`, mapping, manifest and validation report |
| `data/models/all-MiniLM-L6-v2/` | Complete local model directory, including weights, tokenizer, configuration and snapshot metadata |
| `var/metadata.sqlite` | Application metadata database for filtering and authors |

Keep the matching directories intact. Startup checks their compatibility; it does not download models or rebuild indexes. Retain `data/evaluation/` for the evaluation page.

### Start the backend

From the project root:

```powershell
.\.venv\Scripts\python.exe -m backend.api
```

The backend runs at `http://127.0.0.1:8000`. Open [API documentation](http://127.0.0.1:8000/docs) or [check readiness](http://127.0.0.1:8000/api/v1/health/ready).

### Start the frontend

Open another PowerShell terminal at the project root:

```powershell
cd frontend
npm run dev
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000). Keep both terminals running; press `Ctrl+C` to stop each server.

The frontend uses the backend's default address. If changing it, set `NEXT_PUBLIC_API_BASE_URL` in `frontend/.env.local` and allow the frontend origin through backend `CORS_ORIGINS`.

## Evaluation

Evaluation compares all four retrieval methods using five queries and 110 manually reviewed query–paper relevance grades. Grades are stored in `data/evaluation/relevance_judgments.csv`: **0** irrelevant, **1** partially relevant and **2** highly relevant. Original rankings are stored in `rankings.json`.

From the project root, calculate results with:

```powershell
.\.venv\Scripts\python.exe -m backend.evaluation.csv_evaluation evaluate
```

The command validates the judgments and writes `data/evaluation/results.json`. Refresh [the Evaluation page](http://127.0.0.1:3000/evaluation) to view Precision@10, Pooled Recall@10, MAP@10, nDCG@10 and precision–recall curves. Keep the completed judgments and saved rankings; blank grades leave evaluation pending.
