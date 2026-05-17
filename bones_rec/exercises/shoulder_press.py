"""
Жим над головой (Shoulder Press).

Отслеживаемый угол: плечевой сустав (бедро → плечо → локоть).
Правая сторона: landmarks 24, 12, 14.
Рука поднимается вверх — угол увеличивается (UP),
рука опускается — угол уменьшается (DOWN).
"""

from base_exercise import BaseExercise
from utils import get_point


class ShoulderPress(BaseExercise):
    """
    Подсчёт жима над головой.

    Уровни сложности:
    - easy:   угол плеча < 100° = DOWN, > 150° = UP
    - medium: угол плеча < 80°  = DOWN, > 160° = UP
    - hard:   угол плеча < 60°  = DOWN, > 170° = UP
    """

    @property
    def name(self) -> str:
        return "Жим над головой"

    @property
    def thresholds(self) -> dict:
        return {
            "easy":   {"down_angle": 100, "up_angle": 150},
            "medium": {"down_angle": 80,  "up_angle": 160},
            "hard":   {"down_angle": 60,  "up_angle": 170},
        }

    def get_landmarks(self, landmarks, w, h) -> dict:
        hip      = get_point(landmarks[24], w, h)  # RIGHT_HIP
        shoulder = get_point(landmarks[12], w, h)  # RIGHT_SHOULDER
        elbow    = get_point(landmarks[14], w, h)  # RIGHT_ELBOW
        return {"a": hip, "b": shoulder, "c": elbow}

    def draw_points(self, frame, points):
        self._draw_line(frame, points["a"], points["b"], (200, 200, 200))
        self._draw_line(frame, points["b"], points["c"], (200, 200, 200))
        self._draw_circle(frame, points["a"], (255, 100, 50))   # бедро
        self._draw_circle(frame, points["b"], (50, 255, 100))   # плечо
        self._draw_circle(frame, points["c"], (50, 100, 255))   # локоть
