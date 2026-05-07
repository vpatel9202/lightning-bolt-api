from datetime import date

from lightning_bolt_api.models import Slot


def test_open_shift_detection() -> None:
    slot = Slot(last_name="z.Administrative", display_name="OPEN 1")

    assert slot.is_open_shift


def test_non_open_shift_detection() -> None:
    slot = Slot(last_name="Smith", display_name="Alex Smith")

    assert not slot.is_open_shift


def test_slot_date_parses_iso_date() -> None:
    slot = Slot(slot_date="2026-05-09")

    assert slot.slot_date == date(2026, 5, 9)


def test_trade_in_detection_from_original_employee() -> None:
    slot = Slot(emp_id=20319, original_emp_id=20066)

    assert slot.is_reassigned
    assert slot.is_trade_in_for(20319)
    assert not slot.is_trade_out_from(20319)
    assert slot.assignment_origin_for(20319) == "trade_in"


def test_trade_out_detection_from_original_employee() -> None:
    slot = Slot(emp_id=20284, original_emp_id=20319)

    assert slot.is_reassigned
    assert not slot.is_trade_in_for(20319)
    assert slot.is_trade_out_from(20319)
    assert slot.assignment_origin_for(20319) == "trade_out"


def test_reassignment_without_perspective_is_unknown() -> None:
    slot = Slot(emp_id=20319, original_emp_id=20066)

    assert slot.assignment_origin_for() == "unknown_reassignment"


def test_scheduler_filled_slot_without_original_employee_is_regular() -> None:
    slot = Slot(emp_id=20319, original_emp_id=None, modified_by_emp_id=20097)

    assert not slot.is_reassigned
    assert slot.assignment_origin_for(20319) == "regular"


def test_slot_history_none_coerces_to_empty_list() -> None:
    slot = Slot(slot_history=None)

    assert slot.slot_history == []
