# Human annotation guide

Open `/evaluation`, review the query collection, select a completed compatible pool, and follow the link to `/evaluation/judge`. Read the query's information need before each judgment. The proposed default collection is not finalized until you review it. If a query changes materially, save another query version and generate a new pool.

Judge title and abstract, using the external ArXiv link if needed. You are assessing whether the paper meets the information need, not whether it contains the same words. No full-PDF download is required.

For the need “methods detecting cancer from medical images,” these are hypothetical criteria examples, not judgments of actual papers:

* **0 — Not relevant:** a paper about telescope image processing mentions detection but does not study cancer or medical images.
* **1 — Partially relevant:** a general medical image segmentation method touches cancer imaging indirectly, without directly evaluating cancer detection.
* **2 — Highly relevant:** the research directly develops or evaluates cancer detection/classification on medical images and the abstract supports that purpose.
* **Unjudged:** the evidence is unclear or you have not assessed the paper. Leave unknown until you can assess it; do not use zero as a substitute for uncertainty.

An abstract sharing several keywords may still be grade 0. A paper using different terminology can be grade 2 when it addresses the need. For ambiguous abstracts, open ArXiv, review the information need, and leave unjudged if evidence is insufficient. Be consistent; avoid judging based on presumed algorithm superiority.

Use radio controls or keys 0/1/2, then **Save judgment**. Keyboard shortcuts are ignored in text fields. No save success is shown until the backend confirms persistence. Save errors preserve your draft and let you retry. **Leave unjudged** followed by Save explicitly clears a previous grade.

By default the session starts at the first unjudged candidate on the current page; successful saves advance to the next unjudged candidate when enabled. Use Previous, Next, Next unjudged, Jump to paper, and the 100-candidate pagination controls for larger pools. Query/pool navigation, pool search, global navigation links, and browser Back ask before discarding a draft. Reload/closing with a dirty relevance grade triggers the browser's standard unsaved-change protection. Save before leaving an annotation session.

Progress comes from persisted data: judged/unjudged counts, percentage, grade distribution, and missing top-K requirements. Export judgments CSV from the annotation view for backup/audit. Algorithm provenance is omitted from the blind view and available only in administrative pool exports.

The initial real top-10 pool contains 622 unique query-paper pairs across 30 queries, with 0 judgments at implementation validation. All 622 require assessment to compare all 30 queries. Counts may change after you change query definitions, filters, or pool depth. The dashboard always computes current readiness from the selected pool.
