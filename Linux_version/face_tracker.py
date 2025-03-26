import mediapipe as mp
import numpy as np
import copy
import time
import math
import cv2

ARROW_MARGIN = 50
MAXIMUM_ANGLE_FOR_OPTIMAL_SETTING = 15


class FaceTracker:

    def __init__(self, width=640, height=480, seconds_before_recenter=10):

        self.__width = width
        self.__height = height

        self.__seconds_before_recenter = seconds_before_recenter

        self.__default_rotation_matrix = np.array([
            [1.0, 0.0, 0.0],
            [0.0, -1.0, 0.0],
            [0.0, 0.0, -1.0]
        ])

        self.__offset_rotation_matrix = np.identity(3)

        self.__current_rotation_matrix = self.__default_rotation_matrix
        self.__lost_face_time = None

        self.__current_frame = None

        self.__cap = cv2.VideoCapture(0)
        self.__cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.__cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

        self.__mp_face_mesh = mp.solutions.face_mesh
        self.__face_mesh = self.__mp_face_mesh.FaceMesh(static_image_mode=False, max_num_faces=1, refine_landmarks=True)
        self.__face_3d = np.array([
            [0.0, 0.0, 0.0],  # Nose
            [0.0, -73.6, -12.0],  # Chin
            [-43.3, 32.7, -20.0],  # Left eye corner
            [43.3, 32.7, -20.0],  # Right eye corner
            [-18.0, -28.9, -24.0],  # Left corner of the mouth
            [18.0, -28.9, -24.0]  # Right corner of the mouth
        ], dtype=np.float64)

        self.__face_2d = None

        self.__face_marks_idxs = [1, 199, 33, 263, 61, 291]

        self.__current_frame_with_positional_arrow = None

    def __calculate_rotation_matrix(self, frame_rgb):
        results = self.__face_mesh.process(frame_rgb)

        if results.multi_face_landmarks:
            face_landmarks = results.multi_face_landmarks[0]
            self.__face_2d = np.array([
                np.array(
                    [face_landmarks.landmark[idx].x * self.__width, face_landmarks.landmark[idx].y * self.__height])
                for idx in self.__face_marks_idxs
            ], dtype=np.float32)

            focal_length = self.__width
            cam_matrix = np.array([
                [focal_length, 0, self.__width / 2],
                [0, focal_length, self.__height / 2],
                [0, 0, 1]
            ], dtype=np.float64)

            dist_coeffs = np.zeros((4, 1))
            success, rot_vec, trans_vec = cv2.solvePnP(self.__face_3d, self.__face_2d, cam_matrix, dist_coeffs,
                                                       flags=cv2.SOLVEPNP_SQPNP)

            if success:
                clean_rotation_matrix, _ = cv2.Rodrigues(rot_vec)
                self.__current_rotation_matrix = self.__offset_rotation_matrix @ clean_rotation_matrix
                self.__lost_face_time = None

        elif self.__lost_face_time is None:
            self.__lost_face_time = time.time()

        return self.__current_rotation_matrix

    def calculate_current_orientation(self):
        ret, frame = self.__cap.read()
        if not ret:
            self.__lost_face_time = time.time()
            return self.__current_rotation_matrix

        h, w, _ = frame.shape
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame_rgb = cv2.flip(frame_rgb, 1)
        self.__current_frame = frame_rgb

        return self.__calculate_rotation_matrix(frame_rgb)

    def find_offset_rotation_matrix(self):
        self.__offset_rotation_matrix = self.__calculate_rotation_matrix(self.__current_frame).T * (-1)

    def reset_rotation_offset(self):
        self.__offset_rotation_matrix = np.identity(3)

    def get_offset_rotation_matrix(self):
        return self.__offset_rotation_matrix

    def get_current_offset_yaw_angle(self):
        return -self.get_current_yaw_angle(rotation_matrix=self.__offset_rotation_matrix)

    def set_offset_rotation_matrix(self, offset_rotation_matrix):
        self.__offset_rotation_matrix = offset_rotation_matrix

    def get_current_orientation(self):
        if self.__lost_face_time and time.time() - self.__lost_face_time >= self.__seconds_before_recenter:
            return copy.deepcopy(self.__default_rotation_matrix)

        return copy.deepcopy(self.__current_rotation_matrix)

    def get_current_yaw_angle(self, rotation_matrix=None):
        if rotation_matrix is None:
            rotation_matrix = self.get_current_orientation()
        return np.degrees(math.atan2(-rotation_matrix[2, 0], math.hypot(rotation_matrix[1, 0], rotation_matrix[0, 0])))

    def get_current_pitch_angle(self, rotation_matrix=None):
        if rotation_matrix is None:
            rotation_matrix = self.get_current_orientation()
        return np.degrees(math.atan2(rotation_matrix[2, 1], math.sqrt(1 - rotation_matrix[2, 0] ** 2)))

    def get_current_roll_angle(self, rotation_matrix=None):
        if rotation_matrix is None:
            rotation_matrix = self.get_current_orientation()
        return np.degrees(math.atan2(rotation_matrix[1, 0], rotation_matrix[0, 0]))

    def get_current_frame(self):
        if self.__current_frame is None:
            ret, frame = self.__cap.read()
            if ret:
                return frame
            else:
                return np.zeros((self.__height, self.__width, 3), dtype=np.uint8)
        else:
            return self.__current_frame

    def check_camera_angle(self, angle):
        return True if abs(angle) <= MAXIMUM_ANGLE_FOR_OPTIMAL_SETTING else False

    def get_current_frame_with_positional_arrow(self, arrow_top_margin=ARROW_MARGIN):
        self.__current_frame_with_positional_arrow = copy.deepcopy(self.__current_frame)

        if self.__face_2d is None:
            no_signal_frame = np.zeros((self.__height, self.__width, 3), dtype=np.uint8)
            cv2.putText(no_signal_frame, "NO CAMERA SIGNAL....", (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (229, 0, 70), 2)
            cv2.putText(no_signal_frame, "CONNECT CAMERA AND", (20, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (229, 0, 70), 2)
            cv2.putText(no_signal_frame, "RESTART  APPLICATION", (20, 120), cv2.FONT_HERSHEY_SIMPLEX,0.8, (229, 0, 70), 2)
            return no_signal_frame

        nose_2d_coordinates = self.__face_2d[0]

        yaw_angle = self.get_current_yaw_angle()
        pitch_angle = self.get_current_pitch_angle()

        arrow_start_point = (int(nose_2d_coordinates[0]), arrow_top_margin)
        arrow_end_point = (int(arrow_start_point[0] - yaw_angle * 1.2), int(arrow_start_point[1] - pitch_angle * 1.2))

        arrow_color = (70, 191, 63) if abs(yaw_angle) <= MAXIMUM_ANGLE_FOR_OPTIMAL_SETTING else (229, 0, 70)

        cv2.arrowedLine(self.__current_frame_with_positional_arrow, arrow_start_point, arrow_end_point, (0, 0, 0), 9)
        cv2.arrowedLine(self.__current_frame_with_positional_arrow, arrow_start_point, arrow_end_point, arrow_color, 5)

        return self.__current_frame_with_positional_arrow

    def cleanup(self):
        self.__cap.release()
