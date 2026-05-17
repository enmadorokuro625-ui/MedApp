"""
Джампинг Джек (Jumping Jacks).

Отслеживаемый угол: угол между корпусом и рукой
(бедро → плечо → запястье).
Правая сторона: landmarks 24, 12, 16.
Руки вверх — угол увеличивается (UP),
руки вниз — угол уменьшается (DOWN).
"""

from base_exercise import BaseExercise
from utils import get_point


class JumpingJacks(BaseExercise):
    """
    Подсчёт прыжков «Джампинг Джек».

    Уровни сложности:
    - easy:   угол < 50°  = DOWN, > 140° = UP
    - medium: угол < 40°  = DOWN, > 155° = UP
    - hard:   угол < 30°  = DOWN, > 170° = UP
    """

    @property
    def name(self) -> str:
        return "Джампинг Джек"

    @property
    def thresholds(self) -> dict:
        return {
            "easy":   {"down_angle": 50,  "up_angle": 140},
            "medium": {"down_angle": 40,  "up_angle": 155},
            "hard":   {"down_angle": 30,  "up_angle": 170},
        }

    def get_landmarks(self, landmarks, w, h) -> dict:
        hip      = get_point(landmarks[24], w, h)  # RIGHT_HIP
        shoulder = get_point(landmarks[12], w, h)  # RIGHT_SHOULDER
        wrist    = get_point(landmarks[16], w, h)  # RIGHT_WRIST
        return {"a": hip, "b": shoulder, "c": wrist}

    def draw_points(self, frame, points):
        self._draw_line(frame, points["a"], points["b"], (200, 200, 200))
        self._draw_line(frame, points["b"], points["c"], (200, 200, 200))
        self._draw_circle(frame, points["a"], (255, 100, 50))   # бедро
        self._draw_circle(frame, points["b"], (50, 255, 100))   # плечо
        self._draw_circle(frame, points["c"], (50, 100, 255))   # запястье
