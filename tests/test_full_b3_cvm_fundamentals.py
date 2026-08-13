import pandas as pd
import pytest

from build_full_b3_cvm_fundamentals import _financial_sector, _share_kind, build_full_panel


def test_share_kind_rejects_units_and_preserves_preferred_classes():
    assert _share_kind("ON") == ("ordinary", None)
    assert _share_kind("PNB") == ("preferred_class", "B")
    assert _share_kind("PN EDJ N2") == ("preferred", None)
    with pytest.raises(ValueError, match="unsupported_share_class"):
        _share_kind("UNT")


def test_financial_sector_is_explicit_not_a_generic_company_label():
    assert _financial_sector("Bancos")
    assert _financial_sector("Serviços Financeiros")
    assert not _financial_sector("Construção Civil")


def test_full_panel_requires_dated_b3_and_accepted_cvm_columns():
    with pytest.raises(ValueError, match="universe missing"):
        build_full_panel(pd.DataFrame(), pd.DataFrame(), 2013, 2013)
