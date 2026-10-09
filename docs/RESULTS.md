# Natural-Language SQL Agent — Results Report

**Evaluation date:** 9 October 2026
**Project:** Week 5 Task 2
**Database:** SQLite Chinook

## 1. Objective

Build a natural-language SQL agent that answers database questions using schema inspection, SQL validation, read-only database access, tool-based error correction, and automated evaluation against a predefined golden set.

## 2. System and Dataset

The database contains **11 tables and 15,607 rows**. The golden evaluation set was committed before the agent implementation and contains **30 answerable questions and 5 unanswerable questions**. The agent uses LangGraph, Groq (`openai/gpt-oss-20b`), SQLite, and SQLGlot-based SQL validation. Four tools are available: schema inspection, fuzzy value search, read-only SQL execution, and arithmetic calculation.

## 3. Measured Results

| Measurement                     |    Result |
| ------------------------------- | --------: |
| Local automated tests           | 36 passed |
| Database tables                 |        11 |
| Database rows                   |    15,607 |
| Answerable evaluation questions |        30 |
| Baseline questions passed       |         4 |
| Baseline questions failed       |        26 |
| Baseline reported pass rate     |    13.33% |
| Recorded rate-limit exceptions  |        21 |

The **13.33% result is not a reliable estimate of SQL-agent accuracy**. All 21 recorded `agent_exception` failures contained rate-limit markers from Groq. The evaluation therefore did not adequately measure the agent's reasoning performance.

## 4. Failure Analysis

The original baseline recorded 21 agent exceptions, 4 column mismatches, and 1 case where no SQL was generated. The exception records were inspected and all 21 contained rate-limit markers. Four failed records had generated SQL, while 22 did not; these diagnostic counts describe overlapping aspects of the same failures and should not be added together.

The primary obstacle in the initial experiment was provider rate limiting. A completed evaluation under adequate quota is needed before identifying the largest genuine SQL reasoning failure category.

## 5. Failed Experiment and Lessons

The initial 30-question live evaluation did not complete successfully as a meaningful accuracy measurement because Groq token-per-minute and daily usage limits interrupted agent calls. The observed pass rate was preserved as a baseline rather than discarded or silently replaced.

The next experiment should run the full golden set when adequate quota is available, record completion status, distinguish provider failures from SQL failures, and report the pass rate over completed questions alongside the total completion count.

## 6. Safety and Limitations

The local suite passed 36 tests, including SQL-safety and database-related checks. Five prompt-injection cases have been prepared for destructive SQL, system-prompt disclosure, secret disclosure, instruction override, and SQL-validation bypass. **Their live outcomes have not yet been verified**, so no prompt-injection success rate is claimed.

The current security runner compares database row counts, not complete database contents. Its results should be treated as preliminary until the checks and classification logic are strengthened. Local tests alone do not prove complete security or correct answers for all natural-language questions.

## 7. Conclusion and Next Steps

The project foundation and local tests are in place, but its live accuracy and prompt-injection resistance remain unverified. The next priorities are to strengthen security-result verification, run the live tests when Groq quota permits, classify genuine agent failures, and verify setup instructions from a clean clone. All reported performance claims should be based on reproducible measurements.
