import cv2
import numpy as np
from streamlit_webrtc import VideoProcessorBase

# Resilient MediaPipe import
try:
    import mediapipe as mp
    from mediapipe.python.solutions import face_mesh as mp_face_mesh
    MP_AVAILABLE = True
except (ImportError, AttributeError):
    try:
        import mediapipe.solutions.face_mesh as mp_face_mesh
        MP_AVAILABLE = True
    except (ImportError, AttributeError):
        try:
            import mediapipe as mp
            mp_face_mesh = mp.solutions.face_mesh
            MP_AVAILABLE = True
        except (ImportError, AttributeError):
            MP_AVAILABLE = False

class EyeTrackingProcessor(VideoProcessorBase):
    def __init__(self):
        self.face_mesh = None
        if MP_AVAILABLE:
            try:
                self.face_mesh = mp_face_mesh.FaceMesh(
                    max_num_faces=1,
                    refine_landmarks=True,
                    min_detection_confidence=0.5,
                    min_tracking_confidence=0.5
                )
            except Exception:
                self.face_mesh = None
        
        self.RIGHT_EYE_OUTER = 33
        self.RIGHT_EYE_INNER = 133
        self.RIGHT_IRIS = [469, 470, 471, 472]
        self.gaze_text = "Tracking disabled" if not MP_AVAILABLE else "No face"

    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")
        h, w, _ = img.shape
        
        if not MP_AVAILABLE or self.face_mesh is None:
            self.gaze_text = "Tracking disabled"
            cv2.putText(img, "MediaPipe not working", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            return frame.from_ndarray(img, format="bgr24")

        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        try:
            results = self.face_mesh.process(rgb)
        except Exception:
            results = None

        self.gaze_text = "No face"

        if results and results.multi_face_landmarks:
            face = results.multi_face_landmarks[0]

            try:
                outer = face.landmark[self.RIGHT_EYE_OUTER]
                inner = face.landmark[self.RIGHT_EYE_INNER]

                outer_x = int(outer.x * w)
                inner_x = int(inner.x * w)

                iris_points = []
                for i in self.RIGHT_IRIS:
                    lm = face.landmark[i]
                    iris_points.append([int(lm.x * w), int(lm.y * h)])

                iris_center = np.mean(iris_points, axis=0).astype(int)

                eye_width = abs(inner_x - outer_x)

                if eye_width > 0:
                    iris_pos = (iris_center[0] - outer_x) / eye_width

                    if iris_pos < 0.40:
                        self.gaze_text = "LOOKING LEFT"
                    elif iris_pos > 0.60:
                        self.gaze_text = "LOOKING RIGHT"
                    else:
                        self.gaze_text = "LOOKING CENTER"

                cv2.circle(img, tuple(iris_center), 4, (0, 255, 0), -1)
            except Exception:
                self.gaze_text = "Error in tracking"

        cv2.putText(img, self.gaze_text, (20, 40),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        return frame.from_ndarray(img, format="bgr24")
