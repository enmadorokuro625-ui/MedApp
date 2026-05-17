"""
Скручивания / подъём корпуса (Sit-ups / Crunches).

Отслеживаемый угол: тазобедренный сустав (плечо → бедро → колено).
Правая сторона: landmarks 12, 24, 26.
Корпус поднимается — угол уменьшается (DOWN),
корпус опускается — угол увеличивается (UP).
"""

from base_exercise import BaseExercise
from utils import get_point


class SitUps(BaseExercise):
    """
    Подсчёт скручиваний (пресс).

    Уровни сложности:
    - easy:   угол бедра < 120° = DOWN, > 155° = UP
    - medium: угол бедра < 100° = DOWN, > 160° = UP
    - hard:   угол бедра < 80°  = DOWN, > 170° = UP
    """

    @property
    def name(self) -> str:
        return "Скручивания"

    @property
    def thresholds(self) -> dict:
        return {
            "easy":   {"down_angle": 120, "up_angle": 155},
            "medium": {"down_angle": 100, "up_angle": 160},
            "hard":   {"down_angle": 80,  "up_angle": 170},
        }

    def get_landmarks(self, landmarks, w, h) -> dict:
        shoulder = get_point(landmarks[12], w, h)  # RIGHT_SHOULDER
        hip      = get_point(landmarks[24], w, h)  # RIGHT_HIP
        knee     = get_point(landmarks[26], w, h)  # RIGHT_KNEE
        return {"a": shoulder, "b": hip, "c": knee}

    def draw_points(self, frame, points):
        self._draw_line(frame, points["a"], points["b"], (200, 200, 200))
        self._draw_line(frame, points["b"], points["c"], (200, 200, 200))
        self._draw_circle(frame, points["a"], (255, 100, 50))   # плечо
        self._draw_circle(frame, points["b"], (50, 255, 100))   # бедро
        self._draw_circle(frame, points["c"], (50, 100, 255))   # колено
