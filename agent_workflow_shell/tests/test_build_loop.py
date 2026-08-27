import pytest

from agent_workflow_shell.build_loop import (
    BuildLoopController,
    BuildReport,
    Criterion,
)


def make_controller(**kwargs):
    criteria = kwargs.pop(
        "criteria",
        [
            Criterion(name="oracle_criterion", is_oracle=True),
            Criterion(name="secondary_criterion"),
        ],
    )
    return BuildLoopController(criteria, **kwargs)


class TestControllerValidation:
    def test_requires_at_least_one_criterion(self):
        with pytest.raises(ValueError):
            BuildLoopController([])

    def test_requires_exactly_one_oracle_none_marked(self):
        with pytest.raises(ValueError):
            BuildLoopController([Criterion(name="a"), Criterion(name="b")])

    def test_requires_exactly_one_oracle_multiple_marked(self):
        with pytest.raises(ValueError):
            BuildLoopController(
                [
                    Criterion(name="a", is_oracle=True),
                    Criterion(name="b", is_oracle=True),
                ]
            )

    def test_rejects_duplicate_criterion_names(self):
        with pytest.raises(ValueError):
            BuildLoopController(
                [
                    Criterion(name="a", is_oracle=True),
                    Criterion(name="a"),
                ]
            )

    def test_max_normal_rounds_must_be_positive(self):
        with pytest.raises(ValueError):
            make_controller(max_normal_rounds=0)

    def test_extension_rounds_cannot_be_negative(self):
        with pytest.raises(ValueError):
            make_controller(extension_rounds=-1)

    def test_default_max_rounds_is_four(self):
        controller = make_controller()
        assert controller.max_rounds == 4


class TestRunLoop:
    def test_all_pass_round_one_stops_immediately(self):
        controller = make_controller()

        def judge_fn(round_number):
            return {"oracle_criterion": True, "secondary_criterion": True}

        report = controller.run(judge_fn)
        assert isinstance(report, BuildReport)
        assert report.status == "VERIFIED"
        assert report.rounds_run == 1
        assert report.unresolved_criteria == ()
        assert report.oracle_passed is True

    def test_always_failing_stops_at_hard_cap_of_four(self):
        controller = make_controller()
        calls = []

        def judge_fn(round_number):
            calls.append(round_number)
            return {"oracle_criterion": False, "secondary_criterion": False}

        report = controller.run(judge_fn)
        assert report.rounds_run == 4
        assert calls == [1, 2, 3, 4]
        assert report.status == "COMPLETE"
        assert set(report.unresolved_criteria) == {
            "oracle_criterion",
            "secondary_criterion",
        }

    def test_no_fifth_round_ever_runs(self):
        controller = make_controller()
        call_count = {"n": 0}

        def judge_fn(round_number):
            call_count["n"] += 1
            return {"oracle_criterion": False, "secondary_criterion": False}

        controller.run(judge_fn)
        assert call_count["n"] == 4

    def test_oracle_failing_alone_still_yields_complete_not_verified(self):
        controller = make_controller()

        def judge_fn(round_number):
            return {"oracle_criterion": False, "secondary_criterion": True}

        report = controller.run(judge_fn)
        assert report.status == "COMPLETE"
        assert report.oracle_passed is False
        assert report.unresolved_criteria == ("oracle_criterion",)

    def test_passes_exactly_on_last_normal_round_skips_extension(self):
        controller = make_controller()

        def judge_fn(round_number):
            passed = round_number >= 3
            return {"oracle_criterion": passed, "secondary_criterion": passed}

        report = controller.run(judge_fn)
        assert report.rounds_run == 3
        assert report.status == "VERIFIED"

    def test_passes_on_extension_round_four(self):
        controller = make_controller()

        def judge_fn(round_number):
            passed = round_number >= 4
            return {"oracle_criterion": passed, "secondary_criterion": passed}

        report = controller.run(judge_fn)
        assert report.rounds_run == 4
        assert report.status == "VERIFIED"

    def test_round_reports_are_captured_for_every_round(self):
        controller = make_controller()

        def judge_fn(round_number):
            return {"oracle_criterion": False, "secondary_criterion": False}

        report = controller.run(judge_fn)
        assert len(report.round_reports) == 4
        assert [r.round_number for r in report.round_reports] == [1, 2, 3, 4]

    def test_judge_fn_returning_unknown_criterion_raises(self):
        controller = make_controller()

        def judge_fn(round_number):
            return {
                "oracle_criterion": True,
                "secondary_criterion": True,
                "made_up_criterion": True,
            }

        with pytest.raises(ValueError):
            controller.run(judge_fn)

    def test_judge_fn_missing_a_criterion_verdict_raises(self):
        controller = make_controller()

        def judge_fn(round_number):
            return {"oracle_criterion": True}

        with pytest.raises(ValueError):
            controller.run(judge_fn)

    def test_judge_fn_returning_non_bool_raises_type_error(self):
        controller = make_controller()

        def judge_fn(round_number):
            return {"oracle_criterion": "partial", "secondary_criterion": True}

        with pytest.raises(TypeError):
            controller.run(judge_fn)

    def test_custom_round_caps_are_respected(self):
        controller = make_controller(max_normal_rounds=1, extension_rounds=0)
        calls = []

        def judge_fn(round_number):
            calls.append(round_number)
            return {"oracle_criterion": False, "secondary_criterion": False}

        report = controller.run(judge_fn)
        assert calls == [1]
        assert report.rounds_run == 1
        assert report.status == "COMPLETE"

    def test_single_criterion_that_is_the_oracle(self):
        controller = BuildLoopController([Criterion(name="only_one", is_oracle=True)])

        def judge_fn(round_number):
            return {"only_one": True}

        report = controller.run(judge_fn)
        assert report.status == "VERIFIED"
        assert report.oracle_passed is True
