import pandas as pd

from cvm_itr import _statement_with_individual_fallback


class FakeArchive:
    def namelist(self):
        return ["itr_cia_aberta_DRE_con_2011.csv", "itr_cia_aberta_DRE_ind_2011.csv"]


def test_individual_statement_is_used_only_when_cnpj_absent_from_consolidated(monkeypatch):
    consolidated = pd.DataFrame({"CNPJ_CIA": ["A"], "VL_CONTA": [1]})
    individual = pd.DataFrame({"CNPJ_CIA": ["A", "B"], "VL_CONTA": [2, 3]})

    def read(_archive, name):
        return consolidated if "_con_" in name else individual

    monkeypatch.setattr("cvm_itr._read_csv_from_zip", read)
    result = _statement_with_individual_fallback(FakeArchive(), "itr_cia_aberta_", "DRE", 2011)

    assert result.to_dict("records") == [{"CNPJ_CIA": "A", "VL_CONTA": 1}, {"CNPJ_CIA": "B", "VL_CONTA": 3}]
