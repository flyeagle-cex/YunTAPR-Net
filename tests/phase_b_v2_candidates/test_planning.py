"""No torch, raw data, checkpoint, gradient, or optimizer fixture."""
from datetime import datetime, timedelta, timezone
import importlib.util
from pathlib import Path
import sys
import pytest

MODULE = Path(__file__).resolve().parents[2] / "scripts/phase_b_v2_candidates/planning.py"
spec = importlib.util.spec_from_file_location("candidate_planning", MODULE)
planning = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = planning
spec.loader.exec_module(planning)


@pytest.mark.parametrize("n,e,u,tail", [(10455,9,47052,1),(10455,17,88876,1),
    (10455,50,261400,1),(20956,9,94302,2),(20956,17,178126,2),(20956,50,523900,2)])
def test_candidate_budget(n, e, u, tail):
    value = planning.budget(n, 2, e)
    assert value.total_updates == u
    assert value.scene_presentations == n * e
    assert value.tail_batch_scenes == tail


@pytest.mark.parametrize("value", [0,-1,True,1.5,"2"])
def test_invalid_integer_rejected(value):
    with pytest.raises(ValueError):
        planning.budget(value, 2, 9)


def test_equal_updates_is_partial_epoch():
    assert planning.update_budget_parts(20956, 2, 47052) == (4, 5140)


def test_batch_greater_than_population_has_no_duplicates():
    result = planning.budget(1, 8, 1)
    assert (result.steps_per_epoch, result.tail_batch_scenes) == (1, 1)


def row(name, role, minutes, year=2023):
    a = datetime(year, 6, 1, tzinfo=timezone.utc) + timedelta(minutes=minutes)
    return planning.RoleSupport(name, role, a-timedelta(minutes=60), a,
                                a-timedelta(minutes=30), a)


def test_same_role_support_overlap_allowed():
    planning.check_role_supports([row("a","Train",60), row("b","Train",90)])


def test_nonoverlapping_candidate_roles():
    planning.check_role_supports([row("a","Train",60), row("b","Calibration",180)])


def test_shared_input_even_without_shared_labels_rejected():
    with pytest.raises(ValueError, match="Shared temporal"):
        planning.check_role_supports([row("a","Train",60),row("b","Calibration",90)])


@pytest.mark.parametrize("year", [2022,2025,2026])
def test_forbidden_years_rejected(year):
    with pytest.raises(ValueError, match="scope year"):
        planning.check_role_supports([row("a","Train",60,year)])


def test_duplicate_identity_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        planning.check_role_supports([row("a","Train",60),row("a","Report",180)])


def test_timezone_required():
    a = datetime(2023,6,1)
    with pytest.raises(ValueError, match="Timezone"):
        planning.check_role_supports([planning.RoleSupport("a","Train",a-timedelta(hours=1),a,a-timedelta(minutes=30),a)])


def test_empty_partition_rejected():
    with pytest.raises(ValueError, match="Empty"):
        planning.check_role_supports([])


def test_single_factor_matrix():
    base = {"gamma":2., "alpha":.5, "lambda_q":1., "lambda_d":0.}
    assert planning.single_factor_changes(base, dict(base,gamma=0.)) == {"gamma"}
    assert planning.single_factor_changes(base, dict(base,lambda_q=2.)) == {"lambda_q"}
    with pytest.raises(ValueError, match="Control"):
        planning.single_factor_changes(base, {"gamma":0.})
