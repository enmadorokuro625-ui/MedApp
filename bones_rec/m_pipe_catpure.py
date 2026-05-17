import cv2
import mediapipe as mp

class CameraStream:
    """Класс для работы с видеопотоком."""
    def __init__(self, camera_index=0):
        self.cap = cv2.VideoCapture(camera_index)
        
    def get_frame(self):
        success, frame = self.cap.read()
        if not success:
            return None
        return frame
    def release(self):
        self.cap.release()

class PoseDetector:
    """Класс для детекции скелета с помощью MediaPipe."""
    def __init__(self):
        self.mp_pose = mp.solutions.pose
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        self.mp_draw = mp.solutions.drawing_utils

    def get_skeleton(self, frame):
        # MediaPipe работает в формате RGB
        img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(img_rgb)
        
        # Возвращаем список точек (landmark) и объект с результатами
        return results.pose_landmarks, results

    def draw_skeleton(self, frame, landmarks):
        """Вспомогательный метод для отрисовки поверх кадра."""
        if landmarks:
            self.mp_draw.draw_landmarks(frame, landmarks, self.mp_pose.POSE_CONNECTIONS)
        return frame

# --- Пример использования ---
if __name__ == "__main__":
    camera = CameraStream()
    detector = PoseDetector()

    while True:
        frame = camera.get_frame()
        if frame is None: break

        landmarks, results = detector.get_skeleton(frame)
        
        # Отрисовка
        annotated_frame = detector.draw_skeleton(frame.copy(), landmarks)
        
        cv2.imshow("Skeleton Tracking", annotated_frame)
        
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    camera.release()
    cv2.destroyAllWindows()