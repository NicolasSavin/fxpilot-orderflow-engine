from app.calculators.value_area import calculate_value_area


def test_value_area_expands_from_poc_to_70_percent():
    result = calculate_value_area({1.0: 10, 1.1: 80, 1.2: 10}, 0.70)
    assert result["val"] == 1.1
    assert result["vah"] == 1.1
    assert result["hvn_levels"] == [1.1]
