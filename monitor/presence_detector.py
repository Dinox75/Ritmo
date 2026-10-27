"""Amostragem opcional da câmera; nenhuma imagem é persistida."""


def detectar_presenca(camera_index=0):
    import cv2
    from cvzone.FaceDetectionModule import FaceDetector

    camera = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    try:
        if not camera.isOpened():
            return "unavailable"
        success, frame = camera.read()
        if not success:
            return "unavailable"
        _, faces = FaceDetector().findFaces(frame, draw=False)
        return "present" if faces else "absent"
    finally:
        camera.release()


def monitorar_presenca(stop_event, interval, emit, camera_index=0):
    previous = None
    while not stop_event.is_set():
        state = detectar_presenca(camera_index)
        if state != previous:
            emit("presence", state, {"camera_index": camera_index})
            previous = state
        stop_event.wait(interval)
