import cv2
import mediapipe as mp
import numpy as np
import math
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

# ---------------------------
# MediaPipe
# ---------------------------

base_options = python.BaseOptions(model_asset_path='pose_landmarker.task')
options = vision.PoseLandmarkerOptions(
    base_options=base_options,
    output_segmentation_masks=False
)
detector = vision.PoseLandmarker.create_from_options(options)

# ---------------------------
# Вспомогательные функции
# ---------------------------

def calculate_angle(a, b, c):
    """
    Вычисляет угол ABC (в точке b)
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
    return [landmark.x * w, landmark.y * h]


# ---------------------------
# Переменные состояния
# ---------------------------

counter = 0
stage = "UP"   # начальное состояние
smoothed_angle = None
alpha = 0.2    # коэффициент сглаживания

# ---------------------------
# Камера
# ---------------------------

cap = cv2.VideoCapture(0)

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

    result = detector.detect(mp_image)

    if result.pose_landmarks:
        landmarks = result.pose_landmarks[0]
        h, w, _ = frame.shape

        # Правая рука (можно поменять на левую при необходимости)
        shoulder = get_point(landmarks[12], w, h)  # RIGHT_SHOULDER
        elbow = get_point(landmarks[14], w, h)     # RIGHT_ELBOW
        wrist = get_point(landmarks[16], w, h)     # RIGHT_WRIST

        angle = calculate_angle(shoulder, elbow, wrist)

        # ---- Сглаживание угла ----
        if smoothed_angle is None:
            smoothed_angle = angle
        else:
            smoothed_angle = alpha * angle + (1 - alpha) * smoothed_angle

        # ---- Логика отжиманий ----
        if stage == "UP":
            if smoothed_angle < 90:
                stage = "DOWN"

        elif stage == "DOWN":
            if smoothed_angle > 160:
                stage = "UP"
                counter += 1

        # ---- Визуализация ----
        cv2.putText(frame,
                    f"Angle: {int(smoothed_angle)}",
                    (30, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (0, 255, 0),
                    2)

        cv2.putText(frame,
                    f"Reps: {counter}",
                    (30, 80),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.2,
                    (0, 0, 255),
                    3)

        cv2.putText(frame,
                    f"Stage: {stage}",
                    (30, 130),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (255, 255, 0),
                    2)

        # Рисуем точки
        cv2.circle(frame, tuple(np.int32(shoulder)), 6, (255, 0, 0), -1)
        cv2.circle(frame, tuple(np.int32(elbow)), 6, (0, 255, 0), -1)
        cv2.circle(frame, tuple(np.int32(wrist)), 6, (0, 0, 255), -1)

    cv2.imshow("Push-up Counter", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()