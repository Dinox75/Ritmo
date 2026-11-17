"""Build capabilities; environment flags cannot add omitted frozen dependencies."""

import json
import sys

from utils.config import ROOT


CAMERA_UNAVAILABLE = ("Este pacote de prévia não inclui câmera nem sensor de presença por webcam. "
                      "O estudo, o sensor de janela e o sensor de entrada continuam disponíveis.")


def _profile():
    if not getattr(sys, "frozen", False):
        return {"profile": "development", "camera": True}
    try:
        profile = json.loads((ROOT / "config" / "capabilities.json").read_text(encoding="utf-8"))
        if profile.get("profile") not in {"preview", "full"} or type(profile.get("camera")) is not bool:
            raise ValueError("invalid capability manifest")
        return profile
    except (OSError, ValueError, AttributeError):
        return {"profile": "unknown", "camera": False}


def camera_available():
    return _profile()["camera"]


def camera_capability():
    return {"available": camera_available(), "profile": _profile()["profile"],
            "detail": "Câmera opcional disponível; requer dispositivo e permissão do Windows."
                      if camera_available() else CAMERA_UNAVAILABLE}


def require_camera():
    if not camera_available():
        raise ValueError(CAMERA_UNAVAILABLE)
