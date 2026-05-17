"""
Базовый абстрактный класс для всех упражнений.
Содержит общую логику: сглаживание угла, подсчёт повторений, уровни сложности.
"""

from abc import ABC, abstractmethod
import cv2
import numpy as np

from utils import calculate_angle


class BaseExercise(ABC):
    """
    Абстрактный класс упражнения.

    Каждое упражнение определяет:
    - name: название
    - thresholds: пороговые углы для каждого уровня сложности
    - get_landmarks(): какие точки тела отслеживать
    - draw_points(): как рисовать точки на кадре

    Уровни сложности:
    - easy   — мягкие пороги, подходит для людей с ограниченной подвижностью
    - medium — стандартные пороги
    - hard   — строгие пороги, полная амплитуда
    """

    DIFFICULTY_EASY = "easy"
    DIFFICULTY_MEDIUM = "medium"
    DIFFICULTY_HARD = "hard"
    VALID_DIFFICULTIES = (DIFFICULTY_EASY, DIFFICULTY_MEDIUM, DIFFICULTY_HARD)

    def __init__(self, difficulty: str = "medium"):
        if difficulty not in self.VALID_DIFFICULTIES:
            raise ValueError(
                f"Неверная сложность '{difficulty}'. "
                f"Допустимые: {self.VALID_DIFFICULTIES}"
            )
        self.difficulty = difficulty
        self.counter = 0
        self.stage = "IDLE"
        self.smoothed_angle = None
        self.alpha = 0.2  # коэффициент EMA-сглаживания

    # ------------------------------------------------------------------
    # Абстрактные свойства и методы — реализуются в подклассах
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Название упражнения для отображения."""
        ...

    @property
    @abstractmethod
    def thresholds(self) -> dict:
        """
        Пороговые углы для каждого уровня сложности.

        Формат:
        {
            "easy":   {"down_angle": ..., "up_angle": ...},
            "medium": {"down_angle": ..., "up_angle": ...},
            "hard":   {"down_angle": ..., "up_angle": ...},
        }

        down_angle — угол, ниже которого фиксируется фаза DOWN.
        up_angle   — угол, выше которого фиксируется фаза UP и засчитывается повтор.
        """
        ...

    @abstractmethod
    def get_landmarks(self, landmarks, w: int, h: int) -> dict:
        """
        Извлекает нужные точки тела из списка landmarks.

        :param landmarks: список pose_landmarks[0] из MediaPipe
        :param w: ширина кадра
        :param h: высота кадра
        :return: dict с ключами 'a', 'b', 'c' — три точки для вычисления угла,
                 и опциональные дополнительные точки для визуализации
        """
        ...

    @abstractmethod
    def draw_points(self, frame, points: dict):
        """
        Рисует ключевые точки и линии на кадре.

        :param frame: кадр OpenCV (BGR)
        :param points: dict точек из get_landmarks()
        """
        ...

    # ------------------------------------------------------------------
    # Общая логика (наследуется всеми упражнениями)
    # ------------------------------------------------------------------

    def _smooth_angle(self, raw_angle: float) -> float:
        """Применяет экспоненциальное скользящее среднее к углу."""
        if self.smoothed_angle is None:
            self.smoothed_angle = raw_angle
        else:
            self.smoothed_angle = (
                self.alpha * raw_angle + (1 - self.alpha) * self.smoothed_angle
            )
        return self.smoothed_angle

    def _get_current_thresholds(self) -> dict:
        """Возвращает пороги для текущего уровня сложности."""
        return self.thresholds[self.difficulty]

    def process_frame(self, landmarks, w: int, h: int) -> dict:
        """
        Основная логика обработки кадра:
        1. Извлечение точек тела
        2. Вычисление угла
        3. Сглаживание
        4. Подсчёт повторений по порогам сложности

        :return: dict с ключами angle, counter, stage
        """
        points = self.get_landmarks(landmarks, w, h)

        raw_angle = calculate_angle(points["a"], points["b"], points["c"])
        angle = self._smooth_angle(raw_angle)

        thresh = self._get_current_thresholds()
        down_angle = thresh["down_angle"]
        up_angle = thresh["up_angle"]

        # Конечный автомат: IDLE → UP → DOWN → UP (повтор) → ...
        if self.stage == "IDLE":
            # Первый кадр — определяем начальное состояние
            if angle > up_angle:
                self.stage = "UP"
            elif angle < down_angle:
                self.stage = "DOWN"

        elif self.stage == "UP":
            if angle < down_angle:
                self.stage = "DOWN"

        elif self.stage == "DOWN":
            if angle > up_angle:
                self.stage = "UP"
                self.counter += 1

        return {
            "angle": angle,
            "counter": self.counter,
            "stage": self.stage,
            "points": points,
        }

    def reset(self):
        """Сброс счётчика и состояния."""
        self.counter = 0
        self.stage = "IDLE"
        self.smoothed_angle = None

    @staticmethod
    def _draw_circle(frame, point, color=(0, 255, 0), radius=6):
        """Рисует кружок на кадре."""
        cv2.circle(frame, tuple(np.int32(point)), radius, color, -1)

    @staticmethod
    def _draw_line(frame, p1, p2, color=(255, 255, 255), thickness=2):
        """Рисует линию между двумя точками."""
        cv2.line(frame, tuple(np.int32(p1)), tuple(np.int32(p2)), color, thickness)

    def get_difficulty_label(self) -> str:
        """Возвращает читаемое название сложности."""
        labels = {
            "easy": "Лёгкий",
            "medium": "Средний",
            "hard": "Сложный",
        }
        return labels.get(self.difficulty, self.difficulty)
