from typing import List, Tuple

import cv2
import numpy as np


_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def detect_faces(frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = _cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(24, 24))
    boxes: List[Tuple[int, int, int, int]] = []
    for (x, y, w, h) in faces:
        boxes.append((int(x), int(y), int(x + w), int(y + h)))
    return boxes


def redact_faces(frames: List[np.ndarray]) -> List[np.ndarray]:
    output: List[np.ndarray] = []
    for frame in frames:
        boxes = detect_faces(frame)
        blurred = frame.copy()
        for x1, y1, x2, y2 in boxes:
            roi = blurred[y1:y2, x1:x2]
            if roi.size == 0:
                continue
            blurred_roi = cv2.GaussianBlur(roi, (21, 21), 0)
            blurred[y1:y2, x1:x2] = blurred_roi
        output.append(blurred)
    return output
