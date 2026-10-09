from datetime import date

from app.services.certificate_pdf import generate_certificate_pdf


def _make(path, **overrides):
    args = dict(
        recipient_name="Asha Verma",
        title="Python Bootcamp",
        issued_by="Acme Academy",
        issue_date=date(2026, 10, 1),
        certificate_id="abc-123",
    )
    args.update(overrides)
    generate_certificate_pdf(path, **args)


def test_generates_valid_pdf_and_leaves_no_temp_file(tmp_path):
    out = tmp_path / "cert.pdf"
    _make(out)
    assert out.read_bytes().startswith(b"%PDF")
    assert not list(tmp_path.glob("*.tmp"))


def test_long_inputs_do_not_break_layout(tmp_path):
    out = tmp_path / "long.pdf"
    _make(out, recipient_name="W" * 80, title="Very long course title " * 5, issued_by="O" * 100)
    assert out.stat().st_size > 0


def test_failure_cleans_up_partial_file(tmp_path):
    out = tmp_path / "bad.pdf"
    try:
        _make(out, issue_date=None)  # .strftime on None -> raises mid-render
    except AttributeError:
        pass
    assert not out.exists()
    assert not list(tmp_path.glob("*.tmp"))
