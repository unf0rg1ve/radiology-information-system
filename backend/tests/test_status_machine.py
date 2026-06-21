"""
Tests for Order status state machine (F2.3).
Covers all valid and invalid transitions from ТЗ раздел 7.
"""
import pytest
from app.services.status_machine import (
    validate_status_transition,
    InvalidStatusTransition,
    VALID_TRANSITIONS,
    STATUS_LABELS,
    is_terminal_status,
    get_allowed_transitions,
)


class TestValidTransitions:
    """Test that all defined valid transitions pass validation."""

    def test_new_to_scheduled(self):
        validate_status_transition("NEW", "SCHEDULED")

    def test_new_to_cancelled(self):
        validate_status_transition("NEW", "CANCELLED")

    def test_scheduled_to_arrived(self):
        validate_status_transition("SCHEDULED", "ARRIVED")

    def test_scheduled_to_cancelled(self):
        validate_status_transition("SCHEDULED", "CANCELLED")

    def test_arrived_to_in_progress(self):
        validate_status_transition("ARRIVED", "IN_PROGRESS")

    def test_arrived_to_cancelled(self):
        validate_status_transition("ARRIVED", "CANCELLED")

    def test_in_progress_to_acquired(self):
        validate_status_transition("IN_PROGRESS", "ACQUIRED")

    def test_in_progress_to_cancelled(self):
        validate_status_transition("IN_PROGRESS", "CANCELLED")

    def test_acquired_to_to_report(self):
        validate_status_transition("ACQUIRED", "TO_REPORT")

    def test_acquired_to_in_progress_retake(self):
        """ACQUIRED → IN_PROGRESS при RETAKE."""
        validate_status_transition("ACQUIRED", "IN_PROGRESS")

    def test_to_report_to_reporting(self):
        validate_status_transition("TO_REPORT", "REPORTING")

    def test_reporting_to_signed(self):
        validate_status_transition("REPORTING", "SIGNED")

    def test_signed_to_issued(self):
        validate_status_transition("SIGNED", "ISSUED")

    def test_issued_to_reporting_for_new_version(self):
        validate_status_transition("ISSUED", "REPORTING")

    def test_same_status_idempotent(self):
        """Transition to same status should be allowed (idempotent)."""
        validate_status_transition("NEW", "NEW")
        validate_status_transition("SCHEDULED", "SCHEDULED")
        validate_status_transition("ISSUED", "ISSUED")


class TestInvalidTransitions:
    """Test that invalid transitions raise InvalidStatusTransition."""

    def test_new_to_issued(self):
        with pytest.raises(InvalidStatusTransition) as exc_info:
            validate_status_transition("NEW", "ISSUED")
        assert "Недопустимый переход" in str(exc_info.value)

    def test_new_to_in_progress(self):
        with pytest.raises(InvalidStatusTransition):
            validate_status_transition("NEW", "IN_PROGRESS")

    def test_scheduled_to_acquired(self):
        with pytest.raises(InvalidStatusTransition):
            validate_status_transition("SCHEDULED", "ACQUIRED")

    def test_arrived_to_signed(self):
        with pytest.raises(InvalidStatusTransition):
            validate_status_transition("ARRIVED", "SIGNED")

    def test_issued_to_any(self):
        """ISSUED is a terminal status — no transitions out."""
        with pytest.raises(InvalidStatusTransition):
            validate_status_transition("ISSUED", "NEW")
        with pytest.raises(InvalidStatusTransition):
            validate_status_transition("ISSUED", "SCHEDULED")

    def test_cancelled_to_any(self):
        """CANCELLED is a terminal status — no transitions out."""
        with pytest.raises(InvalidStatusTransition):
            validate_status_transition("CANCELLED", "NEW")
        with pytest.raises(InvalidStatusTransition):
            validate_status_transition("CANCELLED", "SCHEDULED")

    def test_signed_to_cancelled(self):
        """Cannot cancel a signed order."""
        with pytest.raises(InvalidStatusTransition):
            validate_status_transition("SIGNED", "CANCELLED")

    def test_issued_to_cancelled(self):
        """Cannot cancel an issued order."""
        with pytest.raises(InvalidStatusTransition):
            validate_status_transition("ISSUED", "CANCELLED")

    def test_to_report_to_cancelled(self):
        """Cannot cancel an order that is already to report."""
        with pytest.raises(InvalidStatusTransition):
            validate_status_transition("TO_REPORT", "CANCELLED")

    def test_reporting_to_cancelled(self):
        """Cannot cancel an order that is being reported."""
        with pytest.raises(InvalidStatusTransition):
            validate_status_transition("REPORTING", "CANCELLED")


class TestHelperFunctions:
    """Test helper functions."""

    def test_is_terminal_status(self):
        assert is_terminal_status("ISSUED") is True
        assert is_terminal_status("CANCELLED") is True
        assert is_terminal_status("NEW") is False
        assert is_terminal_status("SIGNED") is False

    def test_get_allowed_transitions(self):
        assert "SCHEDULED" in get_allowed_transitions("NEW")
        assert "CANCELLED" in get_allowed_transitions("NEW")
        assert get_allowed_transitions("ISSUED") == {"REPORTING"}
        assert get_allowed_transitions("CANCELLED") == set()

    def test_all_statuses_have_labels(self):
        """Every status in VALID_TRANSITIONS should have a Russian label."""
        for status in VALID_TRANSITIONS:
            assert status in STATUS_LABELS, f"Missing label for status: {status}"

    def test_main_flow_sequence(self):
        """Test the complete main flow: NEW → ... → ISSUED."""
        flow = ["NEW", "SCHEDULED", "ARRIVED", "IN_PROGRESS", "ACQUIRED", "TO_REPORT", "REPORTING", "SIGNED", "ISSUED"]
        for i in range(len(flow) - 1):
            validate_status_transition(flow[i], flow[i + 1])
