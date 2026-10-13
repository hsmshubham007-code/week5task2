from src.agent import SYSTEM_PROMPT


def test_invoice_count_ranking_requires_customer_id_and_columns():
    prompt = SYSTEM_PROMPT.lower()
    rule = prompt.split("18. customer invoice-count rankings:", 1)[1]
    rule = rule.split("19. customer spending rankings:", 1)[0]

    for expected in (
        "customerid",
        "firstname",
        "lastname",
        "invoice_count",
        "count(i.invoiceid)",
        "order by invoice_count desc and customerid asc",
    ):
        assert expected in rule


def test_customer_spending_ranking_requires_customer_id_and_columns():
    prompt = SYSTEM_PROMPT.lower()
    rule = prompt.split("19. customer spending rankings:", 1)[1]
    rule = rule.split("20. for customer support representatives:", 1)[0]

    for expected in (
        "customerid",
        "firstname",
        "lastname",
        "total_spent",
        "invoice.total",
        "lastname asc",
        "firstname asc",
    ):
        assert expected in rule


def test_general_id_rule_allows_explicit_evaluation_exceptions():
    prompt = SYSTEM_PROMPT.lower()
    rule = prompt.split("11. return only the columns", 1)[1]
    rule = rule.split("12. use clear aliases", 1)[0]

    assert "explicitly required" in rule
    assert "rules 18 and 19" in rule