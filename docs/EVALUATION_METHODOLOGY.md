# IR evaluation methodology

The system implements evaluation software; genuine academic effectiveness results require human assessment. Default information needs are proposed topics, not labels, and must be reviewed for representation in this sampled corpus. No rank, retrieval score, or model output serves as ground truth.

## Pooling and assessment

Use the top 10 of TF-IDF, BM25, Semantic, and Hybrid RRF under identical filters. Deduplicate stable ArXiv IDs per query. A depth-20 pool is recommended for stronger judged-set recall analysis. Grades: 0 not relevant; 1 partial/indirect relevance; 2 substantial direct relevance. Unjudged means unknown and never equals 0. Assessors see the information need, title, full abstract, author/category/date metadata, and external ArXiv link in deterministic shuffled order without method, rank, or score.

The shared eligible-query set requires complete judgments for the union of all four top-K lists. Incomplete queries are excluded together for all four methods; a request with zero eligible queries returns 409 and creates no completed run. A partially judged extended pool may still meet top-K coverage: recall and ideal DCG then use only known grades, and remaining unknown pool documents are disclosed in progress. Pool/index/configuration mismatch and insufficient pool depth reject evaluation.

## Metrics

Binary relevance is grade >= 1 by default; threshold 2 is configurable. Original grades always remain intact for nDCG.

* P@K = relevant retrieved within K / K. If retrieval returns fewer than K papers, the denominator remains K (fixed-cutoff, missing retrieval positions contribute zero). This does not convert an unjudged retrieved paper to non-relevant.
* Pooled Recall@K = relevant retrieved within K / R, where R is the number of known relevant papers in this pool snapshot. This is not exhaustive recall over the 50,000-paper corpus. R=0 makes recall unavailable (`null`).
* AP@K = sum of prefix precisions at relevant ranks <=K / min(R,K). R=0 makes AP unavailable. MAP@K is the arithmetic macro mean of defined AP@K values across the shared eligible-query set.
* DCG@K = sum of `(2^grade - 1)/log2(rank+1)` for ranks starting at 1.
* nDCG@K = DCG / IDCG, with ideal grades sorted over the judged pool snapshot. Zero IDCG makes nDCG unavailable.

Top-K missing judgments make all final effectiveness metrics unavailable for the affected query. All-zero judgments differ from missing judgments: P@K and DCG are zero; recall/AP/nDCG may be undefined. Aggregates report the defined-query count for every metric and population standard deviation. Four methods use the same eligible query set and threshold; undefined-denominator exclusions are shared because all methods use the same pool grades. No statistical significance or universal winner is inferred from mean differences.

## Precision–recall curves

Per-query curves contain actual prefix precision and pooled recall at each returned rank up to K. They are discrete measurements, joined by straight lines for readability, with no smoothing or interpolation. Queries with R=0 have unavailable recall. Aggregate curves take macro mean precision and pooled recall at each rank across the same eligible queries with defined recall. For queries with fewer returned documents, aggregate points use zero contribution from empty later ranking positions while retaining the accumulated relevant count. Configurable K cannot exceed frozen pool depth and requires corresponding judgment coverage.

## Hand-check example

Ranking A,B,C,D with grades 2,0,1,2 and an additional judged relevant paper E(1) gives R=4. At K=10: P=.3; pooled recall=.75; AP=(1+2/3+3/4)/4=0.6041666667. DCG=3+1/2+3/log2(5). IDCG=3+3/log2(3)+1/2+1/log2(5). Changing binary threshold to 2 gives P=.2, recall=1, AP=(1+2/4)/2=.75, with identical graded nDCG. Tests assert these exact formulas.

## Limitations

Pooling reduces single-retriever bias but misses relevant papers beyond the contributing lists. Pool membership, assessors, interpretation of ambiguous abstracts, sampled corpus coverage, and shallow pool depth all affect results. Known-relevant denominators may grow after deeper assessment. Version pools and snapshot grades; compare like configurations. A single assessor provides no inter-assessor agreement estimate. Test fixture grades verify software only and are isolated from the production evaluation database.
