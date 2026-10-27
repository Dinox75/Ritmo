"""Descoberta não invasiva e teste de imagem somente por pedido explícito."""

import base64
import json
import subprocess
import sys


def _directshow_devices():
    if sys.platform != "win32":
        return None
    try:
        import comtypes
        from pygrabber.dshow_graph import FilterGraph
        comtypes.CoInitialize()
        try:
            return [str(name) for name in FilterGraph().get_input_devices()]
        finally:
            comtypes.CoUninitialize()
    except Exception:
        # A enumeração é opcional: drivers/COM podem falhar sem impedir o app.
        return None


def windows_devices():
    indexed = _directshow_devices()
    if indexed is not None:
        return indexed
    if sys.platform != "win32":
        return []
    script = ("Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | "
              "Where-Object { $_.Class -in @('Camera','Image') } | "
              "Select-Object -ExpandProperty FriendlyName | ConvertTo-Json -Compress")
    try:
        result = subprocess.run(["powershell", "-NoProfile", "-Command", script],
                                capture_output=True, text=True, timeout=8,
                                creationflags=subprocess.CREATE_NO_WINDOW, check=False)
        if result.returncode or not result.stdout.strip():
            return []
        names = json.loads(result.stdout)
        return [str(name) for name in (names if isinstance(names, list) else [names]) if name]
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return []


def camera_options():
    indexed = _directshow_devices()
    return {"devices": indexed if indexed is not None else windows_devices(),
            "indexed": indexed is not None, "indices": list(range(6)),
            "mapping": "Nomes enumerados pelo DirectShow; confirme cada opção pelo teste de imagem." if indexed is not None
                       else "O Windows informou nomes sem associação confiável aos índices; teste a imagem."}


def _privacy_denied():
    if sys.platform != "win32":
        return False
    try:
        import winreg
        key = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\webcam"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as registry:
            return winreg.QueryValueEx(registry, "Value")[0] == "Deny"
    except OSError:
        return False


def test_camera(index, *, names=None):
    if type(index) is not int or not 0 <= index <= 5:
        raise ValueError("índice de câmera deve estar entre 0 e 5")
    if _privacy_denied():
        return {"status": "no_permission", "detail": "O Windows bloqueou o acesso à webcam."}
    import cv2
    try:
        camera = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    except Exception as failure:
        return {"status": "failure", "detail": f"Não foi possível iniciar a câmera {index}: {failure}"}
    try:
        if not camera.isOpened():
            indexed = _directshow_devices() if names is None else None
            if indexed is not None and index >= len(indexed):
                return {"status": "not_found", "detail": f"Câmera {index} não encontrada no DirectShow."}
            known = indexed if indexed is not None else (windows_devices() if names is None else names)
            if not known:
                return {"status": "not_found", "detail": "Nenhuma câmera foi identificada no Windows."}
            return {"status": "unavailable", "detail": "Não foi possível abrir este índice. A câmera pode estar ocupada, sem permissão ou ausente."}
        try:
            success, frame = camera.read()
        except Exception as failure:
            return {"status": "failure", "detail": f"A câmera abriu, mas a leitura falhou: {failure}"}
        if not success or frame is None:
            return {"status": "failure", "detail": "A câmera abriu, mas não forneceu imagem."}
        height, width = frame.shape[:2]
        if width > 640:
            frame = cv2.resize(frame, (640, round(height * 640 / width)))
        encoded, image = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
        if not encoded:
            return {"status": "failure", "detail": "Não foi possível exibir a imagem capturada."}
        return {"status": "ready", "detail": f"Imagem da câmera {index} capturada para este teste.",
                "image": "data:image/jpeg;base64," + base64.b64encode(image.tobytes()).decode("ascii")}
    finally:
        camera.release()
