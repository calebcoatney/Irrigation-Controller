import os
import serial

COMMANDS: dict[tuple[int, str], bytes] = {
    (1, "open"):  b'\xA0\x01\x01\xA2',
    (1, "close"): b'\xA0\x01\x00\xA1',
    (2, "open"):  b'\xA0\x02\x01\xA3',
    (2, "close"): b'\xA0\x02\x00\xA2',
}

PORT = "/dev/irrigation_relay"
BAUD = 9600


class RelayError(Exception):
    pass


class RelayController:
    def __init__(self, port: str = PORT):
        self.port = port
        self._state: dict[int, str] = {1: "closed", 2: "closed"}

    def _send(self, data: bytes) -> None:
        try:
            with serial.Serial(self.port, BAUD, timeout=1) as ser:
                ser.write(data)
        except serial.SerialException as e:
            raise RelayError(str(e)) from e

    def open_valve(self, valve_id: int) -> None:
        self._send(COMMANDS[(valve_id, "open")])
        self._state[valve_id] = "open"

    def close_valve(self, valve_id: int) -> None:
        self._send(COMMANDS[(valve_id, "close")])
        self._state[valve_id] = "closed"

    @property
    def status(self) -> dict[str, str]:
        return {"valve_1": self._state[1], "valve_2": self._state[2]}

    @property
    def available(self) -> bool:
        return os.path.exists(self.port)
