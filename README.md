# Natural-Language SQL Agent

A read-only natural-language-to-SQL agent built with Python, LangGraph, Groq, and SQLite. The agent translates questions into SQL, executes permitted queries against the Chinook sample database, and uses tool errors to help correct failed SQL.

## Project Status

* **Database:** SQLite Chinook
* **Tables:** 11
* **Rows:** 15,607
* **LLM provider:** Groq
* **Default model:** `openai/gpt-oss-20b`
* **Automated local tests:** 49 passed
* **Golden evaluation set:** 30 answerable questions and 5 unanswerable questions
* **Live prompt-injection evaluation:** Not yet completed

The project is under development. The baseline evaluation was affected by Groq rate limits, so its score should not be interpreted as a reliable measure of SQL-agent accuracy.

## Features

* Natural-language questions translated into SQL.
* Read-only SQLite access.
* SQL validation before execution.
* Rejection of destructive statements and multiple SQL statements.
* Automatic row limits on query results.
* Schema inspection and fuzzy value search.
* Safe arithmetic calculator tool.
* LangGraph-based tool-calling workflow.
* Error feedback to support SQL correction.
* Automated evaluation against a predefined golden set.
* JSON and CSV evaluation reports.
* Prompt-injection test cases for five attack categories.

## Architecture

1. **User question:** The user asks a database question in natural language.
2. **Agent:** LangGraph coordinates the model and available tools.
3. **Schema inspection:** The agent can inspect tables, columns, and foreign-key relationships.
4. **SQL generation:** The model produces a read-only SQL query.
5. **Validation:** The SQL safety layer parses and validates the query before execution.
6. **Database execution:** SQLite executes approved queries using a read-only connection.
7. **Error correction:** Tool errors are returned to the agent so it can attempt a correction.
8. **Response:** The agent returns its answer, generated SQL, and tool logs.
9. **Evaluation:** The evaluation script compares returned data with expected results from the golden set.

## Technology Stack

| Component           | Technology     |
| ------------------- | -------------- |
| Language            | Python 3.12    |
| LLM provider        | Groq           |
| Agent orchestration | LangGraph      |
| Model integration   | LangChain Groq |
| Database            | SQLite         |
| SQL validation      | SQLGlot        |
| Configuration       | python-dotenv  |
| Testing             | pytest         |

## Project Structure

```text
week5task2/
├── data/
│   └── chinook.db
├── docs/
│   └── SCHEMA.md
├── evals/
│   ├── build_golden_set.py
│   ├── golden_set.json
│   ├── questions.py
│   ├── evaluate_agent.py
│   ├── failure_taxonomy.json
│   ├── results.json
│   ├── results.csv
│   ├── results_baseline.json
│   ├── results_baseline.csv
│   └── test_prompt_injection.py
├── src/
│   ├── agent.py
│   ├── agent_tools.py
│   ├── calculator.py
│   ├── database.py
│   ├── inspect_schema.py
│   ├── schema_tools.py
│   └── sql_safety.py
├── tests/
├── verify_database.py
├── verify_rock_count.py
├── requirements.txt
├── .env.example
└── README.md
```

Some evaluation output files are generated when evaluation scripts run. The baseline files preserve the original evaluation results.

## Prerequisites

* Windows, macOS, or Linux
* Python 3.12
* Git
* A Groq API key for live agent calls

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/hsmshubham007-code/week5task2.git
cd week5task2
```

Replace the placeholder with the actual repository URL.

### 2. Create a virtual environment

On Windows PowerShell:

```powershell
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure environment variables

Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

Add your own Groq API key to `.env`:

```dotenv
GROQ_API_KEY=your_groq_api_key_here
GROQ_MODEL=openai/gpt-oss-20b
```

Never commit `.env` or publish API keys. Keep credentials in environment variables.

### 4. Verify the database

```powershell
python verify_database.py
```

The current database contains 11 tables and 15,607 rows. The verification script reports table-level row counts.

### 5. Run automated tests

```powershell
python -m pytest -q
```

The current recorded local result is **49 passed**. Re-run the tests after making changes.

## Available Agent Tools

The agent exposes four tools:

1. `inspect_database_schema` — inspects database tables, columns, and relationships.
2. `search_database_values` — searches for matching database values, including fuzzy substring matches.
3. `execute_readonly_sql` — validates and executes permitted SQL queries.
4. `arithmetic_calculator` — evaluates supported arithmetic expressions safely.

## SQL Safety

The database access layer uses a read-only SQLite connection and a SQL validation layer.

The safety layer is designed to:

* Permit read-only queries.
* Reject destructive SQL such as `DROP`, `DELETE`, `UPDATE`, and `INSERT`.
* Reject multiple statements.
* Reject administrative statements such as `PRAGMA`.
* Apply a maximum row limit.
* Use database-level restrictions as an additional defense.

These controls reduce risk but do not establish that every possible attack is prevented. Security claims must be supported by tests and recorded outcomes.

## Golden Evaluation Set

The predefined evaluation set contains:

* 30 answerable questions.
* 5 unanswerable questions.
* Expected SQL, expected columns, and expected rows.

The golden set was committed before the agent implementation so that evaluation expectations were established independently of the agent.

Evaluation compares returned result data rather than requiring the generated SQL text to match the reference query exactly. Column aliases may differ, and tied results may appear in different orders where the scoring logic permits it.

Do not modify the expected answers simply to increase the score. If a reference answer is genuinely incorrect, document and justify the correction separately.

## Evaluation Commands

Run the answerable-question evaluation:

```powershell
python .\evals\evaluate_agent.py
```

Retry eligible incomplete or transient failures using the evaluator's resume option:

```powershell
python .\evals\evaluate_agent.py --resume
```

The evaluator writes JSON and CSV reports under `evals/`. Review the completed-question count and failure categories before reporting the pass rate.

**Important:** Live evaluation makes Groq API calls and may consume token quota. Provider rate limits can cause incomplete runs. Do not interpret rate-limit failures as SQL reasoning failures.

## Recorded Baseline

The first evaluation attempt produced these results:

| Metric               | Recorded baseline |
| -------------------- | ----------------: |
| Answerable questions |                30 |
| Passed               |                 4 |
| Failed               |                26 |
| Reported pass rate   |            13.33% |
| Agent exceptions     |                21 |
| Column mismatches    |                 4 |
| No SQL generated     |                 1 |

The run was heavily affected by Groq rate limits, including token-per-minute and daily token limits. Therefore, **13.33% is an incomplete, rate-limit-confounded baseline, not a trustworthy estimate of the agent's underlying accuracy**.

The preserved baseline files are `evals/results_baseline.json` and `evals/results_baseline.csv`. A later evaluation should report completed questions, rate-limit failures, and the measured pass rate separately.

### Latest Evaluation Attempt — 2026-10-12

A subsequent live evaluation produced 30 question records, but all 30 were blocked by Groq rate limits. This run does not measure SQL-agent accuracy.

An offline rescore using saved results could evaluate only 8 of the 30 questions. All 8 rescored questions passed (8/8); the remaining 22 had no usable saved result for rescoring. The 100% pass rate applies only to the rescored subset, not the complete evaluation set.

Evidence files:

- `evals/results_rate_limited.json` — latest rate-limit-confounded live run.
- `evals/results_rescored.json` — offline rescore summary.
- `evals/results_rescored.csv` — per-question rescore status.

A reliable overall accuracy result still requires usable results for all 30 answerable questions.

## Failure Analysis

The evaluation reports classify failures into categories such as:

* Agent exceptions and provider rate limits.
* Column mismatches.
* Missing generated SQL.
* SQL execution errors.
* Missing or malformed SQL results.
* Result-data mismatches.

The next improvement should target the largest category after separating infrastructure failures from genuine agent failures.

## Prompt-Injection Evaluation

Five attack cases are defined in `evals/test_prompt_injection.py`:

1. Attempt to execute destructive SQL.
2. Request disclosure of the hidden system prompt.
3. Request environment variables and credentials.
4. Attempt to override the read-only policy.
5. Attempt to bypass SQL validation with multiple statements.

Run the tests with:

```powershell
python .\evals\test_prompt_injection.py
```

This command makes live Groq calls. It may consume quota and stops early if a rate limit is detected.

The script records outcomes in `evals/prompt_injection_results.json` and `evals/prompt_injection_results.csv`. Do not report an attack as successfully blocked unless the recorded evidence supports that conclusion. An inconclusive run is not a passing security test.

## Database Integrity Verification

Run:

```powershell
python verify_database.py
```

This reports the number of tables and the row count of each table.

A separate query verification script is available:

```powershell
python verify_rock_count.py
```

The expected Rock-track count recorded during local verification is 1,297. These scripts provide useful checks, but row counts alone cannot detect every possible database modification.

## Limitations

* The initial live evaluation was affected by provider rate limits.
* A reliable, completed 30-question evaluation is still required.
* The five prompt-injection cases have been defined, but their live outcomes must be measured before making security claims.
* The prompt-injection fingerprint currently compares table row counts, not complete database contents.
* Results depend on the configured model, its available quota, and model-generated SQL.
* A passing local test suite does not guarantee perfect SQL accuracy or immunity to prompt injection.

## Current Verification Summary

* Database verified: 11 tables and 15,607 rows.
* Local automated tests: 49 passed.
* Golden set: 30 answerable and 5 unanswerable questions.
* Live evaluation: baseline incomplete due to rate limits.
* Live prompt-injection outcomes: pending.
* Clean-clone setup: must be verified from a fresh clone before claiming reproducibility.

## License and Dataset

The project uses the Chinook sample database. Check the applicable dataset license and attribution requirements before redistribution. Add a project license if one is required for your submission.
