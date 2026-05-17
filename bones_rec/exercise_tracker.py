"""
Главный трекер упражнений.

Объединяет камеру, MediaPipe Pose Landmarker и объект упражнения.
Запускает цикл обработки видеопотока с подсчётом повторений.
"""

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from base_exercise import BaseExercise


class ExerciseTracker:
    """
    Трекер упражнений.

    Инициализирует камеру и MediaPipe PoseLandmarker,
    запускает основной цикл обработки кадров.
    """

    def __init__(
        self,
        exercise: BaseExercise,
        camera_index: int = 0,
        model_path: str = "pose_landmarker.task",
    ):
        """
        :param exercise: объект упражнения (наследник BaseExercise)
        :param camera_index: индекс камеры (0 — встроенная)
        :param model_path: путь к модели pose_landmarker.task
        """
        self.exercise = exercise
        self.camera_index = camera_index

        # Инициализация MediaPipe PoseLandmarker
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            output_segmentation_masks=False,
        )
        self.detector = vision.PoseLandmarker.create_from_options(options)

    def _draw_hud(self, frame, info: dict):
        """
        Отрисовывает HUD (heads-up display) с информацией:
        название упражнения, сложность, угол, повторения, стадия.
        """
        h, w, _ = frame.shape

        # Полупрозрачная панель сверху
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (w, 160), (30, 30, 30), -1)
        cv2.addWeighted(overlay, 0.6, frame, 0.4, 0, frame)

        # Название упражнения и сложность
        label = f"{self.exercise.name}  |  {self.exercise.get_difficulty_label()}"
        cv2.putText(
            frame, label, (20, 35),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2,
        )

        # Угол
        angle_text = f"Угол: {int(info['angle'])}"
        cv2.putText(
            frame, angle_text, (20, 70),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 180), 2,
        )

        # Повторения
        reps_text = f"Повторения: {info['counter']}"
        cv2.putText(
            frame, reps_text, (20, 110),
            cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 120, 255), 3,
        )

        # Стадия
        stage_color = (100, 255, 100) if info["stage"] == "UP" else (100, 100, 255)
        cv2.putText(
            frame, f"Фаза: {info['stage']}", (20, 145),
            cv2.FONT_HERSHEY_SIMPLEX, 0.7, stage_color, 2,
        )

    def run(self):
        """Запуск основного цикла трекинга."""
        cap = cv2.VideoCapture(self.camera_index)

        if not cap.isOpened():
            print("Ошибка: не удалось открыть камеру.")
            return

        window_name = f"Exercise Tracker — {self.exercise.name}"
        print(f"\n▶ Запуск: {self.exercise.name} "
              f"(сложность: {self.exercise.get_difficulty_label()})")
        print("  Нажмите ESC для выхода, R для сброса счётчика.\n")

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            # Конвертация для MediaPipe
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

            # Детекция позы
            result = self.detector.detect(mp_image)

            if result.pose_landmarks:
                landmarks = result.pose_landmarks[0]
                h, w, _ = frame.shape

                # Обработка кадра через упражнение
                info = self.exercise.process_frame(landmarks, w, h)

                # Рисуем точки упражнения
                self.exercise.draw_points(frame, info["points"])

                # Рисуем HUD
                self._draw_hud(frame, info)

            cv2.imshow(window_name, frame)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                break
            elif key == ord("r") or key == ord("R"):
                self.exercise.reset()
                print("  ↺ Счётчик сброшен.")

        cap.release()
        cv2.destroyAllWindows()

        print(f"\n✓ Завершено. Итого повторений: {self.exercise.counter}")
