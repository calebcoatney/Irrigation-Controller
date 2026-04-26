from relay import RelayController

_relay = RelayController()


def get_relay() -> RelayController:
    return _relay
