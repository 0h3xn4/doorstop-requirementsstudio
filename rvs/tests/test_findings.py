from rvs_core.findings import Finding, Severity, sort_findings


def test_sorted_by_severity_then_location_then_code():
    a = Finding("B-1", Severity.WARNING, "w", location="SYS/SYS-0001.yml")
    b = Finding("A-1", Severity.ERROR, "e", location="z.yml")
    c = Finding("A-2", Severity.INFO, "i")
    d = Finding("A-0", Severity.ERROR, "e2", location="a.yml")
    assert sort_findings([a, b, c, d]) == [d, b, a, c]


def test_finding_renders_what_where_and_what_to_do():
    f = Finding(
        "RVS-X", Severity.ERROR, "Bad value.", hint="Use one of: a, b.", location="SYS/SYS-0001.yml", uid="SYS-0001"
    )
    text = f.format()
    assert "SYS-0001" in text and "Bad value." in text and "Use one of: a, b." in text
    assert "Traceback" not in text
