from unittest.mock import patch
from relay import RelayController, COMMANDS


def test_initial_state_both_closed():
    ctrl = RelayController(port="/dev/fake")
    assert ctrl.status == {"valve_1": "closed", "valve_2": "closed"}


def test_command_table_has_all_four_commands():
    assert (1, "open") in COMMANDS
    assert (1, "close") in COMMANDS
    assert (2, "open") in COMMANDS
    assert (2, "close") in COMMANDS


def test_open_valve_1_sends_correct_bytes():
    ctrl = RelayController(port="/dev/fake")
    with patch("relay.serial.Serial") as MockSerial:
        mock_ser = MockSerial.return_value.__enter__.return_value
        ctrl.open_valve(1)
        mock_ser.write.assert_called_once_with(b'\xA0\x01\x01\xA2')


def test_open_valve_2_sends_correct_bytes():
    ctrl = RelayController(port="/dev/fake")
    with patch("relay.serial.Serial") as MockSerial:
        mock_ser = MockSerial.return_value.__enter__.return_value
        ctrl.open_valve(2)
        mock_ser.write.assert_called_once_with(b'\xA0\x02\x01\xA3')


def test_close_valve_1_sends_correct_bytes():
    ctrl = RelayController(port="/dev/fake")
    with patch("relay.serial.Serial") as MockSerial:
        mock_ser = MockSerial.return_value.__enter__.return_value
        ctrl.close_valve(1)
        mock_ser.write.assert_called_once_with(b'\xA0\x01\x00\xA1')


def test_close_valve_2_sends_correct_bytes():
    ctrl = RelayController(port="/dev/fake")
    with patch("relay.serial.Serial") as MockSerial:
        mock_ser = MockSerial.return_value.__enter__.return_value
        ctrl.close_valve(2)
        mock_ser.write.assert_called_once_with(b'\xA0\x02\x00\xA2')


def test_open_valve_updates_state():
    ctrl = RelayController(port="/dev/fake")
    with patch("relay.serial.Serial"):
        ctrl.open_valve(1)
    assert ctrl.status["valve_1"] == "open"
    assert ctrl.status["valve_2"] == "closed"


def test_close_valve_updates_state():
    ctrl = RelayController(port="/dev/fake")
    with patch("relay.serial.Serial"):
        ctrl.open_valve(2)
        ctrl.close_valve(2)
    assert ctrl.status["valve_2"] == "closed"


def test_available_false_when_port_missing():
    ctrl = RelayController(port="/dev/nonexistent_irrigation_device")
    assert ctrl.available is False
