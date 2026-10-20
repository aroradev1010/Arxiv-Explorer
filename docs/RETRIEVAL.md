# Online retrieval over verified indexes

The offline corpus and artifacts are reused as-is. All methods map positions through the same sorted `doc_ids.json`. The loader checks that both mapping files, manifest fingerprints and SQLite IDs/positions agree. The API does not rebuild indexes, refit vocabulary, alter IDF, change the model revision or resave any artifacts.

TF-IDF uses the existing count vectorizer and TF-IDF transformer, including conservative LaTeX cleanup, NFKC, Porter stemming, stopword policy, sublinear TF, smoothed IDF and L2 normalization. Sparse document rows are multiplied by the persisted query vector. Only an N-element score vector is dense. Zero-overlap lexical queries return no matches. Filtering restricts rows/candidates before selecting top-K.

BM25 wraps the existing tested CSC posting scorer. It retains corpus-wide document frequencies, nonnegative Robertson IDF, average length, k1=1.5 and b=.75. Unique query terms are scored once. Eligible positions restrict final candidates before top-K; corpus statistics are never recalculated for a filtered subset.

Semantic queries use the pipeline's `clean` function and the already downloaded original PyTorch Sentence Transformer with `normalize_embeddings=True`. The model revision/file hashes, 384 dimensions and 256-token setting match the verified corpus embeddings. The existing corpus combines equivalent full-precision PyTorch and OpenVINO vectors, whose consistency was validated in the prior phase. Query inference is initialized once and serialized by a lock.

Unfiltered retrieval searches the existing FAISS IndexFlatIP. The boundary is expanded if needed to include tied scores before deterministic ID ordering. Filtered retrieval computes exact inner products over the eligible saved normalized embedding rows, in chunks of 4,096; it never filters a global top-10 list after ranking. An eligible set containing all documents follows the FAISS path so its results agree exactly with unfiltered retrieval. Score ties follow ascending sorted ID/position. Query shape/norm/finiteness, empty eligibility and FAISS sentinel results are handled explicitly.

For hybrid retrieval:

```
RRF(d) = sum(1 / (k + rank_i(d)))
k = 60; candidate depth per native ranker = 200
```

Ranks are 1-based. Missing rankers contribute zero. Duplicate appearances within one ranker count once; conflicting ID/position mappings are rejected. `math.fsum` prevents accumulation order from breaking symmetric ties. Final ordering is descending score then ascending ArXiv ID. Each contribution and native score is exposed; native scores are not normalized and added together. A native mode requested alongside hybrid can retrieve a wider window once, with RRF using only its first 200 ranks.

Recommendations query FAISS with the existing source-document vector, remove the source ID, then rerank contiguously and batch-load metadata. No model call or training is required.

These checks establish mathematical implementation and mapping/filter correctness. They do not establish that hybrid is more relevant than individual methods. Precision, recall, MAP and nDCG require genuine relevance judgments in a later evaluation phase.
