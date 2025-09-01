# Thin wrapper so that `from Client.gateway import Gateway` works
from gateway.gateway_ws import Gateway

__all__ = ["Gateway"]
