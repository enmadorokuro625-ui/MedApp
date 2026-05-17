"""
Отжимания (Push-ups).

Отслеживаемый угол: локоть (плечо → локоть → запястье).
Правая сторона: landmarks 12, 14, 16.
"""

import cv2

from base_exercise import BaseExercise
from utils import get_point


class PushUps(BaseExercise):
    """
    Подсчёт отжиманий.

    Уровни сложности:
    - easy:   угол локтя < 110° = DOWN, > 150° = UP
    - medium: угол локтя < 90°  = DOWN, > 160° = UP
    - hard:   угол локтя < 70°  = DOWN, > 170° = UP
    """

    @property
    def name(self) -> str:
        return "Отжимания"

    @property
    def thresholds(self) -> dict:
        return {
            "easy":   {"down_angle": 110, "up_angle": 150},
            "medium": {"down_angle": 90,  "up_angle": 160},
            "hard":   {"down_angle": 70,  "up_angle": 170},
        }

    def get_landmarks(self, landmarks, w, h) -> dict:
        shoulder = get_point(landmarks[12], w, h)  # RIGHT_SHOULDER
        elbow    = get_point(landmarks[14], w, h)  # RIGHT_ELBOW
        wrist    = get_point(landmarks[16], w, h)  # RIGHT_WRIST
        return {"a": shoulder, "b": elbow, "c": wrist}

    def draw_points(self, frame, points):
        self._draw_line(frame, points["a"], points["b"], (200, 200, 200))
        self._draw_line(frame, points["b"], points["c"], (200, 200, 200))
        self._draw_circle(frame, points["a"], (255, 100, 50))   # плечо
        self._draw_circle(frame, points["b"], (50, 255, 100))   # локоть
        self._draw_circle(frame, points["c"], (50, 100, 255))   # запястье
