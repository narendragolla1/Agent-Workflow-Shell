import pytest

from agent_workflow_shell.fix_escalation import (
    EscalationDecision,
    check_confidence_gate,
    should_escalate_to_spec,
)


class TestShouldEscalateToSpec:
    def test_below_threshold_does_not_escalate(self):
        decision = should_escalate_to_spec({"a.py", "b.py"})
        assert decision.escalate is False

    def test_at_default_threshold_escalates(self):
        decision = should_escalate_to_spec({"a.py", "b.py", "c.py"})
        assert decision.escalate is True
        assert "3" in decision.reason or "files" in decision.reason.lower()

    def test_one_below_default_threshold_does_not_escalate(self):
        decision = should_escalate_to_spec({"a.py", "b.py"})
        assert decision.escalate is False

    def test_above_threshold_escalates(self):
        decision = should_escalate_to_spec({"a.py", "b.py", "c.py", "d.py"})
        assert decision.escalate is True

    def test_empty_file_set_does_not_escalate_on_its_own(self):
        decision = should_escalate_to_spec(set())
        assert decision.escalate is False

    def test_duplicate_paths_are_deduped_before_counting(self):
        # a list with duplicates should behave like a set of unique files
        decision = should_escalate_to_spec(["a.py", "a.py", "b.py"])
        assert decision.escalate is False

    def test_architectural_change_flag_forces_escalation_even_with_one_file(self):
        decision = should_escalate_to_spec({"a.py"}, architectural_change=True)
        assert decision.escalate is True
        assert "architect" in decision.reason.lower()

    def test_custom_threshold_is_respected(self):
        decision = should_escalate_to_spec({"a.py", "b.py"}, threshold=2)
        assert decision.escalate is True

    def test_custom_threshold_below_two_raises(self):
        with pytest.raises(ValueError):
            should_escalate_to_spec({"a.py"}, threshold=0)

    def test_negative_threshold_raises(self):
        with pytest.raises(ValueError):
            should_escalate_to_spec({"a.py"}, threshold=-1)

    def test_decision_is_a_namedtuple_like_dataclass_with_reason(self):
        decision = should_escalate_to_spec({"a.py", "b.py", "c.py"})
        assert isinstance(decision, EscalationDecision)
        assert isinstance(decision.reason, str) and decision.reason

    def test_not_escalating_still_has_a_reason(self):
        decision = should_escalate_to_spec({"a.py"})
        assert decision.escalate is False
        assert isinstance(decision.reason, str) and decision.reason


class TestConfidenceGate:
    @pytest.mark.parametrize("level", ["High", "high", "HIGH", "Medium", "medium"])
    def test_high_and_medium_confidence_do_not_block(self, level):
        assert check_confidence_gate(level) is True

    @pytest.mark.parametrize("level", ["Low", "low", "LOW"])
    def test_low_confidence_blocks(self, level):
        assert check_confidence_gate(level) is False

    def test_unknown_confidence_level_raises(self):
        with pytest.raises(ValueError):
            check_confidence_gate("Certain")

    def test_empty_confidence_level_raises(self):
        with pytest.raises(ValueError):
            check_confidence_gate("")

    def test_confidence_level_with_surrounding_whitespace_is_normalized(self):
        assert check_confidence_gate("  High  ") is True
        assert check_confidence_gate("  low ") is False
