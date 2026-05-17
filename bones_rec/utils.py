"""
Утилиты для вычисления углов и извлечения координат из MediaPipe landmarks.
"""

import numpy as np


def calculate_angle(a, b, c):
    """
    Вычисляет угол ABC (в точке b) в градусах.

    :param a: координаты первой точки [x, y]
    :param b: координаты вершины угла [x, y]
    :param c: координаты третьей точки [x, y]
    :return: угол в градусах (0–180)
    """
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)

    ba = a - b
    bc = c - b

    cosine = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
    angle = np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))

    return angle


def get_point(landmark, w, h):
    """
    Преобразует нормализованные координаты landmark в пиксельные.

    :param landmark: объект landmark из MediaPipe
    :param w: ширина кадра
    :param h: высота кадра
    :return: [x, y] в пикселях
    """
    return [landmark.x * w, landmark.y * h]
