from core.widgets.services.quick_launch.providers.currency import _rebase_to_eur


def test_rebase_to_eur_handles_both_orientations_and_skips_non_reference_rows():
    rows = [
        {"base": "GBP", "quote": "USD", "type": "reference", "value": 1.25},
        {"base": "EUR", "quote": "GBP", "type": "reference", "value": 0.8},
        {"base": "GBP", "quote": "JPY", "type": "buy", "value": 190.0},
        {"base": "GBP", "quote": "CHF", "type": "reference", "value": 0},
        {"base": "GBP", "quote": "SEK", "type": "reference", "value": "x"},
    ]
    rates = _rebase_to_eur(rows, "GBP")
    assert rates is not None
    assert rates["GBP"] == 0.8
    assert rates["USD"] == 1.0  # 1 EUR = 0.8 GBP = 1 USD
    assert set(rates) == {"GBP", "USD"}


def test_rebase_to_eur_needs_a_euro_rate():
    assert _rebase_to_eur([{"base": "GBP", "quote": "USD", "type": "reference", "value": 1.25}], "GBP") is None
    assert _rebase_to_eur([], "GBP") is None
