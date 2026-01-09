from typing import Dict, List, Tuple

import cv2
import numpy as np


def draw_boxes(frame: np.ndarray, boxes: List[Tuple[int, int, int, int]], labels: List[str]) -> np.ndarray:
    annotated = frame.copy()
    for box, label in zip(boxes, labels):
        x1, y1, x2, y2 = box
        cv2.rectangle(annotated, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            annotated,
            label,
            (x1, max(0, y1 - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            1,
            cv2.LINE_AA,
        )
    return annotated


def draw_polygon(frame: np.ndarray, polygon: List[Tuple[int, int]]) -> np.ndarray:
    annotated = frame.copy()
    pts = np.array(polygon, dtype=np.int32).reshape((-1, 1, 2))
    cv2.polylines(annotated, [pts], isClosed=True, color=(0, 0, 255), thickness=2)
    return annotated


def blur_regions(frame: np.ndarray, regions: List[Tuple[int, int, int, int]]) -> np.ndarray:
    output = frame.copy()
    for x1, y1, x2, y2 in regions:
        roi = output[y1:y2, x1:x2]
        if roi.size == 0:
            continue
        blurred = cv2.GaussianBlur(roi, (15, 15), 0)
        output[y1:y2, x1:x2] = blurred
    return output


def contact_sheet(images: Dict[str, np.ndarray]) -> np.ndarray:
    tiles = []
    for name, img in images.items():
        canvas = img.copy()
        cv2.putText(canvas, name, (5, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        tiles.append(canvas)
    if not tiles:
        raise ValueError("No images to combine")
    h, w = tiles[0].shape[:2]
    sheet = np.zeros((h * len(tiles), w, 3), dtype=np.uint8)
    for idx, tile in enumerate(tiles):
        sheet[idx * h : (idx + 1) * h] = tile
    return sheet
