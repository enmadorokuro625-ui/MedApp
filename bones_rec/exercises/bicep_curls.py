"""
Сгибание на бицепс (Bicep Curls).

Отслеживаемый угол: локоть (плечо → локоть → запястье).
Правая сторона: landmarks 12, 14, 16.
Логика инвертирована: рука сгибается (угол уменьшается) = DOWN,
                       рука разгибается (угол увеличивается) = UP.
"""

from base_exercise import BaseExercise
from utils import get_point


class BicepCurls(BaseExercise):
    """
    Подсчёт сгибаний на бицепс.

    Уровни сложности:
    - easy:   угол локтя < 70° = DOWN, > 150° = UP
    - medium: угол локтя < 50° = DOWN, > 160° = UP
    - hard:   угол локтя < 40° = DOWN, > 170° = UP
    """

    @property
    def name(self) -> str:
        return "Сгибание на бицепс"

    @property
    def thresholds(self) -> dict:
        return {
            "easy":   {"down_angle": 70, "up_angle": 150},
            "medium": {"down_angle": 50, "up_angle": 160},
            "hard":   {"down_angle": 40, "up_angle": 170},
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
