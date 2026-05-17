"""
Выпады (Lunges).

Отслеживаемый угол: колено передней ноги (бедро → колено → лодыжка).
Правая сторона: landmarks 24, 26, 28.
Нога сгибается — угол уменьшается (DOWN),
нога выпрямляется — угол увеличивается (UP).
"""

from base_exercise import BaseExercise
from utils import get_point


class Lunges(BaseExercise):
    """
    Подсчёт выпадов.

    Уровни сложности:
    - easy:   угол колена < 130° = DOWN, > 165° = UP
    - medium: угол колена < 110° = DOWN, > 170° = UP
    - hard:   угол колена < 90°  = DOWN, > 175° = UP
    """

    @property
    def name(self) -> str:
        return "Выпады"

    @property
    def thresholds(self) -> dict:
        return {
            "easy":   {"down_angle": 130, "up_angle": 165},
            "medium": {"down_angle": 110, "up_angle": 170},
            "hard":   {"down_angle": 90,  "up_angle": 175},
        }

    def get_landmarks(self, landmarks, w, h) -> dict:
        hip   = get_point(landmarks[24], w, h)  # RIGHT_HIP
        knee  = get_point(landmarks[26], w, h)  # RIGHT_KNEE
        ankle = get_point(landmarks[28], w, h)  # RIGHT_ANKLE
        return {"a": hip, "b": knee, "c": ankle}

    def draw_points(self, frame, points):
        self._draw_line(frame, points["a"], points["b"], (200, 200, 200))
        self._draw_line(frame, points["b"], points["c"], (200, 200, 200))
        self._draw_circle(frame, points["a"], (255, 100, 50))   # бедро
        self._draw_circle(frame, points["b"], (50, 255, 100))   # колено
        self._draw_circle(frame, points["c"], (50, 100, 255))   # лодыжка
