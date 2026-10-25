## The reason of having the validator and validate_warehouse
Why nearly every mature pipeline has both
Six real reasons — not theory:

1. Data is genuinely dirty. Not sometimes — always. Of your two sources, one was clean (population), one had four documented defect categories (exchange rate). If you don't check, you don't know which one you have today.

2. Silent failures are the default. A pipeline can exit 0 and still be wrong:

Loaded 0 rows (empty source)

Wrote 25 rows but 3 columns are NULL

Type cast silently corrupted numbers

Join returned 0 rows — no error, just empty dashboards

No exception thrown ≠ correct. Validation is how you know.

3. Fail-fast is cheaper than debug-later. A null population caught at extraction costs 30 seconds. The same null discovered in a weekly report costs a day of investigation — "is this a source bug? a transform bug? a load bug? which of 8 tables?" Validation localizes the failure.

4. Downstream consumers need a contract. The moment a dbt model reads raw.population_by_province, it assumes a shape: these columns, this type, this row count. validate_warehouse.py is that promise enforced. When the promise breaks, you know immediately — not when the model throws a confusing column does not exist error.

5. Reproducibility across environments. You're on Windows, running locally. In production this would be Linux, scheduled, by a different person. Validation encodes "what 'healthy' means" so anyone can verify any environment.

6. Automation requires exit codes. Airflow doesn't read your print statements. It reads exit codes. A validation script that exits 1 on failure becomes a gate — the next DAG task doesn't run until validation passes. That's how you prevent bad data from reaching production: make the pipeline physically unable to continue past a failed check.



## How to explaining the layer:
Interview framing
Q: "How do you ensure data quality in your pipeline?"

Weak answer: "I check for nulls and duplicates." — describes one check, not a strategy.

Strong answer:

"I layer it. Pure functions validate DataFrames before load — nulls, dtypes, expected counts, contiguity against a canonical set. The extractor fails fast if validation fails, so bad data never reaches the warehouse. After load, a separate health check runs read-only SQL against the warehouse: schema contracts, row counts, reconciliation against source CSVs, and dimension-join integrity. It exits non-zero on failure, so a scheduler or CI can gate on it. Pre-load catches bad data. Post-load catches bad writes and drift. They check different things — you need both."


## The real production system layers!:
unit tests    →  validators.py  →  extractor  →  warehouse  →  validate_warehouse.py  →  dbt tests
  (code)         (pre-load)                       (DB)         (post-load)             (transform)