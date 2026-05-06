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
