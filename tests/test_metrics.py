import numpy as np
import pytest

from app.services.metrics import SceneRejected, calculate_metrics, green_score, priority


def test_proportions_exclude_sky_and_people():
    labels = np.array([[4, 9, 6, 11, 1], [13, 2, 12, 20, 2]])
    result = calculate_metrics(labels)
    assert result.vegetation_percentage == pytest.approx(2 / 6)
    assert result.hard_surface_percentage == pytest.approx(2 / 6)
    assert result.building_percentage == pytest.approx(1 / 6)
    assert result.open_ground_percentage == pytest.approx(1 / 6)
    assert result.classified_coverage == 0.6
    assert result.tree_presence is True
    assert result.green_score == 39


def test_score_uses_the_spec_formula_not_the_illustrative_number():
    assert green_score(0.12, 0.06, True) == 24
    assert green_score(0, 0, False) == 0
    assert green_score(1, 0, True) == 75


@pytest.mark.parametrize('score, expected', [(0, 'HIGH'), (34, 'HIGH'), (35, 'MEDIUM'), (64, 'MEDIUM'), (65, 'LOW'), (100, 'LOW')])
def test_priority_boundaries(score, expected):
    assert priority(score) == expected


@pytest.mark.parametrize('labels', [np.full((10, 10), 2), np.full((10, 10), 3), np.array([])])
def test_unusable_masks_never_create_a_diagnosis(labels):
    with pytest.raises(SceneRejected):
        calculate_metrics(labels)
