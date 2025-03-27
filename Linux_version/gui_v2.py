from PIL import Image, ImageTk, ImageDraw
from screeninfo import get_monitors
import customtkinter as ctk
import sounddevice as sd
import soundfile as sf
import tkinter as tk
import numpy as np
import pulsectl
import math
import copy
import json
import os

import virtual_player as vp
import face_tracker


MIN_APP_WIDTH = 820
MIN_APP_HEIGHT = 510

BUTTON_HEIGHT = 40
CORNER_RADIUS = 12
PADDING_X = 10
PADDING_Y = 10
BORDER_PADDING = 10
RIGHT_FRAME_WIDTH = 355
FONT_SIZE = 15

SPEAKER_CLICK_SOUNDFILE_PATH = "sound/speaker_click.wav"
SINK_NAME = "Virtual_Surround_by_nixpl"
SAVE_FILE_NAME = "Virtual_Surround_settings.json"


def find_sink_by_name(pulse, sink_name):
    for sink in pulse.sink_list():
        if sink.name == sink_name:
            return sink
    return None


def find_sink_by_description(pulse, sink_description):
    for sink in pulse.sink_list():
        if sink.description == sink_description:
            return sink
    return None


def get_appearance_mode_idx():
    return 1 if ctk.get_appearance_mode() == "Dark" else 0


def round_pil_image_corners(pil_image, size, radius=CORNER_RADIUS):
    pil_image = pil_image.resize(size, Image.LANCZOS)

    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, *size), radius, fill=255)

    rounded_pil_image = Image.new("RGBA", size)
    rounded_pil_image.paste(pil_image, (0, 0), mask)

    return rounded_pil_image


class CameraCalibrationFrame(ctk.CTkFrame):
    def __init__(self, master, face_tracker, **kwargs):
        super().__init__(master, **kwargs)

        self.__active = False

        self.__master = master
        self.__face_tracker = face_tracker

        self.__image_label = ctk.CTkLabel(self)
        self.__image_label.grid()

        self.__image_reference = None
        self.__update_image()

        self.__current_frame = None

        self.__info_label = ctk.CTkLabel(self,
                                         text='Camera placement calibration steps:',
                                         font=("Arial", FONT_SIZE, "bold"),
                                         wraplength=RIGHT_FRAME_WIDTH - 4 * PADDING_X, justify="left", anchor="w")
        self.__info_label.grid(row=0, column=0, padx=PADDING_X * 2, pady=(PADDING_Y, PADDING_Y), sticky="nsew")

        self.__info_label = ctk.CTkLabel(self,
                                         text="1 Center camera preview on your main screen:",
                                         font=("Arial", FONT_SIZE),
                                         wraplength=RIGHT_FRAME_WIDTH - 4 * PADDING_X,
                                         justify="left",
                                         anchor="w")
        self.__info_label.grid(row=1, column=0, padx=PADDING_X, pady=(0, PADDING_Y / 2), sticky="nsew")

        self.__center_button = ctk.CTkButton(self, text="Center camera preview", font=("Arial", FONT_SIZE, "bold"),
                                             corner_radius=CORNER_RADIUS,
                                             command=self.__handle_center_button,
                                             height=BUTTON_HEIGHT)

        self.__center_button.grid(row=2, column=0, padx=PADDING_X, pady=(0, PADDING_Y), sticky="nsew")

        self.__info_label = ctk.CTkLabel(self,
                                         text='2 If you see green arrow when you look directly at camera preview, click "Configure". '
                                              'Otherwise set the camera in a more optimal place.',
                                         font=("Arial", FONT_SIZE),
                                         wraplength=RIGHT_FRAME_WIDTH - 4 * PADDING_X,
                                         justify="left",
                                         anchor="w")
        self.__info_label.grid(row=3, column=0, padx=PADDING_X, pady=(0, PADDING_Y / 2), sticky="nsew")

        self.__buttons_frame = ctk.CTkFrame(self, fg_color=self.cget("fg_color"))
        self.__buttons_frame.grid(row=5, column=0, padx=PADDING_X, pady=(PADDING_Y / 2, PADDING_Y), sticky="nsew")
        self.__buttons_frame.grid_columnconfigure(0, weight=1)
        self.__buttons_frame.grid_columnconfigure(1, weight=1)

        self.__configure_button = ctk.CTkButton(self.__buttons_frame, text="Configure",
                                                font=("Arial", FONT_SIZE, "bold"),
                                                corner_radius=CORNER_RADIUS,
                                                command=self.__handle_configure_button,
                                                height=BUTTON_HEIGHT)
        self.__configure_button.grid(row=0, column=0, padx=(0, PADDING_X * 2 / 3), pady=0, sticky="nsew")

        self.__reset_to_default_button = ctk.CTkButton(self.__buttons_frame, text="Reset to default",
                                                       font=("Arial", FONT_SIZE, "bold"),
                                                       corner_radius=CORNER_RADIUS,
                                                       command=self.__handle_reset_to_default_button,
                                                       height=BUTTON_HEIGHT,
                                                       fg_color="#E50046",
                                                       hover_color="#B4003A")
        self.__reset_to_default_button.grid(row=0, column=1, padx=(PADDING_X * 2 / 3, 0), pady=0,
                                            sticky="nsew")

    def __update_image(self):
        if self.__active:
            self.__current_frame = self.__face_tracker.get_current_frame_with_positional_arrow()

            custom_width = RIGHT_FRAME_WIDTH - 4 * PADDING_X
            custom_height = int(custom_width * 3 / 4)
            image_pil = round_pil_image_corners(Image.fromarray(self.__current_frame),
                                                size=(custom_width, custom_height))

            self.__image_reference = ctk.CTkImage(light_image=image_pil, size=(custom_width, custom_height))

            self.__image_label.configure(image=self.__image_reference, text='', )
        self.__image_label.grid(row=4, column=0, padx=PADDING_X, pady=(PADDING_Y / 2, PADDING_Y / 2), sticky="nsew")
        self.after(10, self.__update_image)

    def __handle_center_button(self):
        self.__master.geometry(f"{MIN_APP_WIDTH}x{MIN_APP_HEIGHT}")
        self.__master.center_window(x_offset=self.__master.get_speaker_compas_frame_width() + BORDER_PADDING,
                                    y_offset=self.winfo_height())
        # the second call is needed because .geometry() does not change size immediately
        self.__master.center_window(x_offset=self.__master.get_speaker_compas_frame_width() + BORDER_PADDING,
                                    y_offset=self.winfo_height())

    def __handle_configure_button(self):
        self.__face_tracker.find_offset_rotation_matrix()
        self.__master.activate_options_frame()

    def __handle_reset_to_default_button(self):
        self.__face_tracker.reset_rotation_offset()
        self.__master.activate_options_frame()

    def set_active_state(self, state):
        self.__active = bool(state)


class SpeakerCompasFrame(ctk.CTkFrame):
    def __init__(self, master, options_frame, face_tracker, **kwargs):
        super().__init__(master, **kwargs)

        self.__face_tracker = face_tracker
        self.__speaker_click_sound_data, self.__speaker_click_sound_samplerate = sf.read(SPEAKER_CLICK_SOUNDFILE_PATH)

        self.__speaker_icons = {}
        self.__speaker_darker_icons = {}
        self.__speaker_icon_ids = {}
        self.__arrow_icon = None
        self.__camera_icon = None

        self.__camera_calibration = False
        self.__camera_icon_distance = 0

        self._cx = 0
        self._cy = 0

        self.__user_icon_size = None
        self.__arrow_icon_size = None
        self.__camera_icon_size = None
        self.__speaker_icon_size = None

        self.__selected_surround_system = master.get_selected_surround_system()
        self.__speakers_parameters = master.get_speakers_parameters()
        self.__surround_system_dict_sounddevice_order = master.get_surround_system_dict_sounddevice_order()
        self.__options_frame = options_frame

        self.__current_appearance_mode = ctk.get_appearance_mode()

        self.__speaker_compas_canvas = tk.Canvas(self, highlightthickness=0)
        self.__speaker_compas_canvas.bind("<Button-1>", self.__handle_speaker_compas_canvas_background_click)
        self.__speaker_compas_canvas.grid(row=0, column=0, padx=BORDER_PADDING * 2, pady=BORDER_PADDING * 2,
                                          sticky="nsew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.__user_icon_png = Image.open("images/user_icon.png").resize((200, 200))
        self.__arrow_icon_png = Image.open("images/arrow_icon.png").resize((200, 200))

        self.__camera_image_idx = 2
        self.__camera_icon_pngs = [
            [
                Image.open(f"images/light_mode/camera_icon_red.png").resize((200, 200)),
                Image.open(f"images/light_mode/camera_icon_green.png").resize((200, 200)),
                Image.open(f"images/light_mode/camera_icon_default.png").resize((200, 200)),
            ],
            [
                Image.open(f"images/dark_mode/camera_icon_red.png").resize((200, 200)),
                Image.open(f"images/dark_mode/camera_icon_green.png").resize((200, 200)),
                Image.open(f"images/dark_mode/camera_icon_default.png").resize((200, 200)),
            ]
        ]

        self.__speaker_icons_pngs = {"light": {}, "dark": {}}
        for i in range(4):
            self.__speaker_icons_pngs["light"][i] = Image.open(f"images/speaker/speaker_{i}.png").resize((200, 200))
            self.__speaker_icons_pngs["dark"][i] = Image.open(f"images/speaker/speaker_dark_{i}.png").resize((200, 200))

        self.__prev_width = 0
        self.__prev_height = 0

        self.draw_speaker_compas()
        self.__draw_camera_icon(self.__face_tracker.get_current_offset_yaw_angle())

        self.__refresh_compas_if_needed()

    def set_options_frame(self, options_frame):
        self.__options_frame = options_frame

    def __handle_speaker_compas_canvas_background_click(self, event):
        clicked_items = self.__speaker_compas_canvas.find_overlapping(event.x, event.y, event.x, event.y)

        if not clicked_items:
            self.__selected_speaker_name = None
            self.__options_frame.draw_speaker_settings()

    def __draw_compas_arrow(self, angle=None):
        if angle is None:
            angle = self.__face_tracker.get_current_yaw_angle()
        self.__arrow_icon = ImageTk.PhotoImage(
            self.__arrow_icon_png.resize((self.__arrow_icon_size, self.__arrow_icon_size)).rotate(angle))
        self.__speaker_compas_canvas.create_image(self.__cx, self.__cy, image=self.__arrow_icon)

    def __draw_camera_icon(self, angle=None, camera_image_idx = 2):
        if angle is None:
            angle = self.__face_tracker.get_current_yaw_angle()
        self.__camera_icon = ImageTk.PhotoImage(
            self.__camera_icon_pngs[get_appearance_mode_idx()][camera_image_idx].resize(
                (self.__camera_icon_size, self.__camera_icon_size)).rotate(-angle))
        self.__speaker_compas_canvas.create_image(
            self.__cx + self.__camera_icon_distance * math.sin(math.radians(angle)),
            self.__cy - self.__camera_icon_distance * math.cos(math.radians(angle)), image=self.__camera_icon)

    def set_camera_calibration(self, state):
        self.__camera_calibration = bool(state)

    def draw_speaker_compas(self):
        appearance_mode = get_appearance_mode_idx()
        self.__speaker_compas_canvas.configure(bg=self.cget("fg_color")[appearance_mode])

        self.__speaker_compas_canvas.delete("all")  # Cleans up old dashed circle

        width = self.__speaker_compas_canvas.winfo_width()
        height = self.__speaker_compas_canvas.winfo_height()

        self.__cx, self.__cy = width // 2, height // 2
        border_len = min(width, height) / 2 - 20
        circle_r = border_len * 0.9

        scalable_unit = int(abs(border_len / 2))

        dashed_line_width = scalable_unit * 0.06
        number_of_dashes = 90
        for i in range(number_of_dashes):
            angle1 = (i * 360 / number_of_dashes)
            angle2 = ((i + 0.5) * 360 / number_of_dashes)

            angle = angle2 - angle1
            angle1 -= angle / 2
            angle2 -= angle / 2

            x1 = self.__cx + circle_r * math.cos(math.radians(angle1))
            y1 = self.__cy + circle_r * math.sin(math.radians(angle1))
            x2 = self.__cx + circle_r * math.cos(math.radians(angle2))
            y2 = self.__cy + circle_r * math.sin(math.radians(angle2))

            self.__speaker_compas_canvas.create_line(x1, y1, x2, y2, width=dashed_line_width,
                                                     fill=self.cget("bg_color")[appearance_mode])

        self.__user_icon_size = int(scalable_unit * 0.55)
        self.__user_icon = ImageTk.PhotoImage(
            self.__user_icon_png.resize((self.__user_icon_size, self.__user_icon_size)))
        self.__speaker_compas_canvas.create_image(self.__cx, self.__cy, image=self.__user_icon)

        self.__arrow_icon_size = int(scalable_unit * 0.9)
        self.__camera_icon_size = scalable_unit // 3
        self.__camera_icon_distance = border_len * 0.9
        self.__draw_arrow_and_camera_icons()


        self.__speaker_icon_size = int(scalable_unit * 0.7)
        speaker_distance = border_len * 0.65
        self.__draw_speakers(self.__selected_surround_system.get(), speaker_distance)

    def __draw_arrow_and_camera_icons(self):
        if self.__camera_calibration:
            self.__draw_compas_arrow(angle=0)
            camera_image_idx = int(self.__face_tracker.check_camera_angle(self.__face_tracker.get_current_yaw_angle()))
            self.__draw_camera_icon(camera_image_idx=camera_image_idx)
        else:
            self.__draw_camera_icon(angle=self.__face_tracker.get_current_offset_yaw_angle())
            self.__draw_compas_arrow()

    def __get_speaker_icon_id(self, volume):
        if volume == 0:
            return 0
        elif volume < 35:
            return 1
        elif volume < 75:
            return 2

        return 3

    def __draw_speaker(self, speaker_name, distance):
        speaker = self.__speakers_parameters.get(speaker_name)
        angle = speaker.get("angle")
        icon_idx = self.__get_speaker_icon_id(speaker.get("volume"))
        self.__speaker_icons[speaker_name] = ImageTk.PhotoImage(
            self.__speaker_icons_pngs.get("light")[icon_idx].resize(
                (self.__speaker_icon_size, self.__speaker_icon_size)).rotate(-angle))
        self.__speaker_darker_icons[speaker_name] = ImageTk.PhotoImage(
            self.__speaker_icons_pngs.get("dark")[icon_idx].resize(
                (self.__speaker_icon_size, self.__speaker_icon_size)).rotate(-angle))

        self.__speaker_icon_ids[speaker_name] = self.__speaker_compas_canvas.create_image(
            self.__cx + distance * math.sin(math.radians(angle)), self.__cy - distance * math.cos(math.radians(angle)),
            image=self.__speaker_icons[speaker_name])
        self.__speaker_compas_canvas.tag_bind(self.__speaker_icon_ids.get(speaker_name), "<Button-1>",
                                              lambda event: self.__handle_speaker_selection(speaker_name))
        self.__speaker_compas_canvas.tag_bind(self.__speaker_icon_ids.get(speaker_name), "<Enter>",
                                              lambda event: self.__speaker_compas_canvas.itemconfig(
                                                  self.__speaker_icon_ids[speaker_name],
                                                  image=self.__speaker_darker_icons[speaker_name]))
        self.__speaker_compas_canvas.tag_bind(self.__speaker_icon_ids.get(speaker_name), "<Leave>",
                                              lambda event: self.__speaker_compas_canvas.itemconfig(
                                                  self.__speaker_icon_ids[speaker_name],
                                                  image=self.__speaker_icons[speaker_name]))

    def __draw_speakers(self, surround_system_choice, distance):
        speaker_names = self.__surround_system_dict_sounddevice_order.get(surround_system_choice)
        for name in speaker_names:
            self.__draw_speaker(name, distance)

    def __draw_speaker_compas_only_when_scaled(self):
        width = self.__speaker_compas_canvas.winfo_width()
        height = self.__speaker_compas_canvas.winfo_height()
        if self.__prev_width == width and self.__prev_height == height:
            return False

        self.__prev_width = width
        self.__prev_height = height
        self.draw_speaker_compas()
        return True

    def __play_click_sound_on_speaker(self, speaker_name, sound_file_path="./sound/speaker_click.wav"):
        speakers_sounddevice_order_list = list(self.__surround_system_dict_sounddevice_order.get("LCR + Rear"))
        num_channels = len(speakers_sounddevice_order_list)
        speaker_channel_index = speakers_sounddevice_order_list.index(speaker_name)
        multi_channel_signal = np.zeros((len(self.__speaker_click_sound_data), num_channels))
        volume = self.__speakers_parameters.get(speaker_name).get("volume") / 100 * 15
        multi_channel_signal[:, speaker_channel_index] = self.__speaker_click_sound_data * volume
        sd.play(multi_channel_signal, self.__speaker_click_sound_samplerate)

    def __handle_speaker_selection(self, speaker_name):
        self.__play_click_sound_on_speaker(speaker_name)
        self.__options_frame.set_selected_speaker_name(speaker_name)
        self.__options_frame.draw_speaker_settings(speaker_name)

    def __refresh_compas_if_needed(self):
        new_appearance_mode = ctk.get_appearance_mode()
        if not self.__draw_speaker_compas_only_when_scaled():
            self.__draw_arrow_and_camera_icons()

        if new_appearance_mode != self.__current_appearance_mode:
            self.__current_appearance_mode = new_appearance_mode
            self.draw_speaker_compas()

        self.after(10, self.__refresh_compas_if_needed)


class OptionsFrame(ctk.CTkFrame):
    def __init__(self, master, speaker_compas_frame, face_tracker, **kwargs):
        super().__init__(master, **kwargs)

        self.__face_tracker = face_tracker

        self.__selected_surround_system = master.get_selected_surround_system()
        self.__speakers_parameters = master.get_speakers_parameters()
        self.__all_speakers_names = [key for key in self.__speakers_parameters.keys()]
        self.__surround_system_dict_sounddevice_order = master.get_surround_system_dict_sounddevice_order()
        self.__default_settings = master.get_default_settings()
        self.__surround_system_options = [key for key in self.__surround_system_dict_sounddevice_order.keys()]
        self.__speaker_compas_frame = speaker_compas_frame
        self.__media_name = master.get_media_name()

        self.__virtual_player = None

        self.__selected_speaker_name = None
        self.__mirroring_on = ctk.BooleanVar(value=True)

        self.__pulse = pulsectl.Pulse()
        self.__output_devices_descriptions = [sink.description for sink in self.__pulse.sink_list() if
                                              sink.name != SINK_NAME]
        default_sink_name = self.__pulse.server_info().default_sink_name
        default_sink_description = find_sink_by_name(self.__pulse, default_sink_name).description

        self.__selected_output_device = ctk.StringVar(value=default_sink_description)

        self.__calibrate_camera_btn = ctk.CTkButton(self, text="Camera calibration",
                                                    font=("Arial", FONT_SIZE, "bold"),
                                                    height=BUTTON_HEIGHT,
                                                    corner_radius=CORNER_RADIUS,
                                                    command=self.master.activate_camera_calibration_frame)
        self.__calibrate_camera_btn.grid(row=0, column=0, padx=PADDING_X, pady=PADDING_Y, sticky="ew")

        self.__headset_dropdown_label = ctk.CTkLabel(self, text="Your headset", font=("Arial", 14, "bold"))
        self.__headset_dropdown_label.grid(row=1, column=0, padx=PADDING_X + CORNER_RADIUS, pady=0, sticky="w")
        self.__headset_dropdown_menu = ctk.CTkOptionMenu(self, values=self.__output_devices_descriptions,
                                                         font=("Arial", FONT_SIZE, "bold"),
                                                         dropdown_font=("Arial", FONT_SIZE, "bold"),
                                                         dropdown_fg_color=('#36719F', '#144870'),
                                                         dropdown_hover_color=('#27577D', '#203A4F'),
                                                         height=BUTTON_HEIGHT,
                                                         corner_radius=CORNER_RADIUS,
                                                         variable=self.__selected_output_device,
                                                         command=self.__start_playing,
                                                         dynamic_resizing=False)
        self.__headset_dropdown_menu.bind("<Button-1>", self.__update_headset_dropdown_values)
        self.__headset_dropdown_menu.grid(row=2, column=0, padx=PADDING_X, pady=0, sticky="ew")

        self.__surround_system_dropdown_label = ctk.CTkLabel(self, text="Surround system",
                                                             font=("Arial", 14, "bold"))
        self.__surround_system_dropdown_label.grid(row=3, column=0, padx=PADDING_X + CORNER_RADIUS, pady=(PADDING_Y, 0),
                                                   sticky="sw")
        self.__surround_system_menu = ctk.CTkOptionMenu(self, values=self.__surround_system_options,
                                                        command=self.__handle_surround_selection,
                                                        font=("Arial", FONT_SIZE, "bold"),
                                                        dropdown_font=("Arial", FONT_SIZE, "bold"),
                                                        dropdown_fg_color=('#36719F', '#144870'),
                                                        dropdown_hover_color=('#27577D', '#203A4F'),
                                                        height=BUTTON_HEIGHT,
                                                        corner_radius=CORNER_RADIUS,
                                                        variable=self.__selected_surround_system)
        self.__surround_system_menu.grid(row=4, column=0, padx=PADDING_X, pady=0, sticky="ew")

        self.__speaker_settings_label = ctk.CTkLabel(self)
        self.grid_rowconfigure(6, weight=1)
        self.__speaker_settings_frame = None
        self.draw_speaker_settings()

        self.__mirror_and_reset_frame = ctk.CTkFrame(self, fg_color=self.cget("fg_color"))
        self.__mirror_and_reset_frame.grid(row=7, column=0, padx=PADDING_X, pady=PADDING_Y, sticky="nsew")
        self.__mirror_and_reset_frame.grid_columnconfigure(0, weight=1)
        self.__mirror_and_reset_frame.grid_columnconfigure(1, weight=1)

        self.__mirror_checkbox = ctk.CTkCheckBox(self.__mirror_and_reset_frame,
                                                 text="Mirror speakers",
                                                 font=("Arial", FONT_SIZE, "bold"),
                                                 corner_radius=int(CORNER_RADIUS * 0.7),
                                                 variable=self.__mirroring_on,
                                                 command=self.__handle_mirror_click)
        self.__mirror_checkbox.grid(row=0, column=0, padx=(0, PADDING_X * 2 / 3), pady=0, sticky="ew")

        self.__reset_changes_btn = ctk.CTkButton(self.__mirror_and_reset_frame,
                                                 text="Reset speakers",
                                                 font=("Arial", FONT_SIZE, "bold"),
                                                 height=BUTTON_HEIGHT,
                                                 corner_radius=CORNER_RADIUS,
                                                 command=self.__handle_reset_btn, fg_color="#E50046",
                                                 hover_color="#B4003A")
        self.__reset_changes_btn.grid(row=0, column=1, padx=(PADDING_X * 2 / 3, 0), pady=0, sticky="ew")

        self.__start_playing()

    def __open_camera_calibration_frame(self):
        frame = CameraCalibrationFrame(self, face_tracker=self.__face_tracker)

    def set_speaker_compas_frame(self, speaker_compas_frame):
        self.__speaker_compas_frame = speaker_compas_frame

    def set_selected_speaker_name(self, speaker_name):
        self.__selected_speaker_name = speaker_name

    def __handle_reset_btn(self):
        self.__selected_speaker_name = None
        default = copy.deepcopy(self.__default_settings.get("speakers_parameters"))
        self.__speakers_parameters.clear()
        self.__speakers_parameters.update(default)
        self.__speaker_compas_frame.draw_speaker_compas()
        self.draw_speaker_settings()

    def __handle_mirror_click(self, value=None):
        if self.__mirroring_on.get():
            leading_side_name = "right"
            if self.__selected_speaker_name is not None and "left" in self.__selected_speaker_name:
                leading_side_name = "left"

            for speaker_name in self.__all_speakers_names:
                if leading_side_name in speaker_name:
                    if speaker_name == self.__selected_speaker_name:
                        self.__speaker_settings_frame.handle_volume_slider(
                            self.__speakers_parameters.get(speaker_name).get("volume"), speaker_name)

                        self.__speaker_settings_frame.handle_angle_slider(
                            self.__speakers_parameters.get(speaker_name).get("angle"), speaker_name)
                    else:
                        self.__speaker_settings_frame.set_speaker_volume_parameter(
                            self.__speakers_parameters.get(speaker_name).get("volume"), speaker_name)
                        self.__speaker_settings_frame.set_speaker_angle_parameter(
                            self.__speakers_parameters.get(speaker_name).get("angle"), speaker_name)
                        self.__speaker_compas_frame.draw_speaker_compas()

    def __update_headset_dropdown_values(self, event):
        self.__headset_dropdown_menu.configure(
            values=[sink.description for sink in self.__pulse.sink_list() if sink.name != SINK_NAME])

    def __start_playing(self, value=None):
        self.close_player()

        headset_name = find_sink_by_description(self.__pulse, self.__selected_output_device.get()).name
        channels_number = len(self.__surround_system_dict_sounddevice_order.get(self.__selected_surround_system.get()))
        self.__virtual_player = vp.VirtualPlayer(pulse=self.__pulse, face_tracker=self.__face_tracker,
                                                 headset_name=headset_name, media_name=self.__media_name, channels_number=channels_number,
                                                 speakers_parameters=self.__speakers_parameters, sink_name=SINK_NAME)
        self.__virtual_player.start_playing()

    def close_player(self):
        if self.__virtual_player is not None:
            self.__virtual_player.stop()

    def __handle_surround_selection(self, value=None):
        self.__selected_speaker_name = None
        self.__start_playing()
        self.__speaker_compas_frame.draw_speaker_compas()
        self.draw_speaker_settings()

    def get_selected_surround_system(self):
        return self.__selected_surround_system

    def draw_speaker_settings(self, speaker_name=""):

        self.__speaker_settings_label.destroy()
        self.__speaker_settings_label = ctk.CTkLabel(self, text="Speaker settings",
                                                     font=("Arial", 14, "bold"))
        if speaker_name != "":
            self.__speaker_settings_label.configure(text=f"{speaker_name} speaker settings")

        self.__speaker_settings_label.grid(row=5, column=0, padx=PADDING_X + CORNER_RADIUS, pady=(PADDING_Y, 0),
                                           sticky="sw")

        self.__speaker_settings_frame = SpeakerSettingsFrame(self, speaker_name=speaker_name, options_frame=self,
                                                             speaker_compas_frame=self.__speaker_compas_frame,
                                                             corner_radius=CORNER_RADIUS)
        self.__speaker_settings_frame.grid(row=6, column=0, padx=PADDING_X, pady=(0, PADDING_Y), sticky="nsew")
        self.__speaker_settings_frame.grid_columnconfigure(0, weight=1)

    def get_mirroring_info(self):
        return self.__mirroring_on

    def get_speakers_parameters(self):
        return self.__speakers_parameters

    def get_surround_system_dict_sounddevice_order(self):
        return self.__surround_system_dict_sounddevice_order


class SpeakerSettingsFrame(ctk.CTkFrame):
    def __init__(self, master, speaker_name, options_frame, speaker_compas_frame, **kwargs):
        super().__init__(master, **kwargs)

        self.__mirroring_on = master.get_mirroring_info()
        self.__speaker_name = speaker_name
        self.__surround_system_dict_sounddevice_order = master.get_surround_system_dict_sounddevice_order()
        self.__speakers_parameters = master.get_speakers_parameters()
        self.__options_frame = options_frame
        self.__speaker_compas_frame = speaker_compas_frame
        self.__selected_surround_system = options_frame.get_selected_surround_system()

        if speaker_name in self.__surround_system_dict_sounddevice_order.get(self.__selected_surround_system.get()):

            self.__speaker_volume_slider_label = ctk.CTkLabel(self,
                                                              text="Volume",
                                                              font=("Arial", FONT_SIZE, "bold"))
            self.__speaker_volume_slider_label.grid(row=0, column=0, padx=2 * PADDING_X, pady=(PADDING_Y, 0),
                                                    sticky="w")
            self.__speaker_volume_slider = ctk.CTkSlider(self, from_=0, to=100,
                                                         number_of_steps=100,
                                                         command=lambda value: self.handle_volume_slider(value,
                                                                                                         speaker_name))
            self.__speaker_volume_slider.set(self.__speakers_parameters.get(speaker_name).get("volume"))
            self.__speaker_volume_slider.grid(row=1, column=0, padx=2 * PADDING_X, pady=(0, 0), sticky="nsew")
            self.__speaker_volume_value_label = ctk.CTkLabel(self,
                                                             text=f"{self.__speakers_parameters.get(speaker_name).get('volume')}%",
                                                             font=("Arial", FONT_SIZE * 2 / 3, "bold"))
            self.__speaker_volume_value_label.grid(row=2, column=0, padx=2 * PADDING_X, pady=(0, 0), sticky="nsew")

            min_angle = self.__speakers_parameters.get(speaker_name).get("min_angle")
            max_angle = self.__speakers_parameters.get(speaker_name).get("max_angle")
            if math.fabs(min_angle) < math.fabs(max_angle):
                self.__speaker_angle_slider_label = ctk.CTkLabel(self, text="Angle",
                                                                 font=("Arial", FONT_SIZE, "bold"))
                self.__speaker_angle_slider_label.grid(row=3, column=0, padx=2 * PADDING_X, pady=(0, 0), sticky="w")
                self.__speaker_angle_slider = ctk.CTkSlider(self, from_=abs(min_angle),
                                                            to=abs(max_angle),
                                                            number_of_steps=abs(max_angle - min_angle),
                                                            command=lambda value: self.handle_angle_slider(value,
                                                                                                           speaker_name))
                self.__speaker_angle_slider.set(abs(self.__speakers_parameters.get(speaker_name).get("angle")))
                self.__speaker_angle_slider.grid(row=4, column=0, padx=2 * PADDING_X, pady=(0, 0), sticky="nsew")
                self.__speaker_angle_value_label = ctk.CTkLabel(self,
                                                                text=f"{abs(self.__speakers_parameters.get(speaker_name).get('angle'))}\u00b0",
                                                                font=("Arial", FONT_SIZE * 2 / 3, "bold"))
                self.__speaker_angle_value_label.grid(row=5, column=0, padx=2 * PADDING_X, pady=(0, PADDING_Y),
                                                      sticky="nsew")

        else:
            self.grid_rowconfigure(0, weight=1)
            self.__select_speaker_label = ctk.CTkLabel(self, text="Select speaker\non compas",
                                                       font=("Arial", 2 * FONT_SIZE, "bold"),
                                                       text_color=self.__options_frame.cget("fg_color"))
            self.__select_speaker_label.grid(row=0, column=0, padx=0, pady=PADDING_Y, sticky="nsew")

    def __find_mirror_speaker_name(self, speaker_name):
        return speaker_name.replace("left", "right") if "left" in speaker_name else speaker_name.replace("right",
                                                                                                         "left")

    def set_speaker_volume_parameter(self, value, speaker_name):
        self.__speakers_parameters[speaker_name]["volume"] = int(value)
        if self.__mirroring_on.get():
            self.__speakers_parameters[self.__find_mirror_speaker_name(speaker_name)]["volume"] = int(value)

    def set_speaker_angle_parameter(self, value, speaker_name):
        self.__speakers_parameters[speaker_name]["angle"] = int(
            math.copysign(value, self.__speakers_parameters.get(speaker_name).get("angle")))
        if self.__mirroring_on.get():
            mirror_speaker_name = self.__find_mirror_speaker_name(speaker_name)
            self.__speakers_parameters[mirror_speaker_name]["angle"] = int(
                math.copysign(value, self.__speakers_parameters.get(mirror_speaker_name).get("angle")))

    def handle_volume_slider(self, value, speaker_name):
        self.set_speaker_volume_parameter(value, speaker_name)
        self.__speaker_volume_value_label.configure(text=f"{int(value)}%")
        self.__speaker_compas_frame.draw_speaker_compas()

    def handle_angle_slider(self, value, speaker_name):
        self.set_speaker_angle_parameter(value, speaker_name)
        self.__speaker_angle_value_label.configure(text=f"{int(abs(value))}\u00b0")
        self.__speaker_compas_frame.draw_speaker_compas()


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Virtual Surround by nixpl")
        self.geometry("850x520")
        self.minsize(MIN_APP_WIDTH, MIN_APP_HEIGHT)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0, minsize=RIGHT_FRAME_WIDTH)

        self.__face_tracker = face_tracker.FaceTracker(width=320, height=240, seconds_before_recenter=10)

        self.__default_settings = {
            "media.name": "Playback Stream",
            "offset_rotation_matrix": [[1.0, 0.0, 0.0],
                                       [0.0, 1.0, 0.0],
                                       [0.0, 0.0, 1.0]],
            "selected_surround_system": "LCR",
            "speakers_parameters": {
                "Front left": {"volume": 100, "angle": -35, "min_angle": -20, "max_angle": -70},
                "Front right": {"volume": 100, "angle": 35, "min_angle": 20, "max_angle": 70},
                "Front center": {"volume": 100, "angle": 0, "min_angle": 0, "max_angle": 0},
                "Rear left": {"volume": 50, "angle": -130, "min_angle": -90, "max_angle": -160},
                "Rear right": {"volume": 50, "angle": 130, "min_angle": 90, "max_angle": 160}
            }
        }

        restored_settings = self.__restore_settings()
        self.__media_name = restored_settings.get("media.name")
        self.__face_tracker.set_offset_rotation_matrix(np.array(restored_settings.get("offset_rotation_matrix")))
        self.__selected_surround_system = ctk.StringVar(value=restored_settings.get("selected_surround_system"))
        self.__speakers_parameters = restored_settings.get("speakers_parameters")

        self.__surround_system_dict_sounddevice_order = {
            "Stereo": ["Front left", "Front right"],
            "LCR": ["Front right", "Front left", "Front center"],
            "LCR + Rear": ["Front left", "Front right", "Rear left", "Rear right", "Front center"]
        }
        self.__camera_calibration_frame = CameraCalibrationFrame(self, face_tracker=self.__face_tracker,
                                                                 width=RIGHT_FRAME_WIDTH, corner_radius=CORNER_RADIUS)

        self.__options_frame = OptionsFrame(self, speaker_compas_frame=None, face_tracker=self.__face_tracker,
                                            width=RIGHT_FRAME_WIDTH,
                                            corner_radius=CORNER_RADIUS)
        self.__options_frame.grid(row=0, column=1, padx=(BORDER_PADDING / 2, BORDER_PADDING),
                                  pady=(BORDER_PADDING, BORDER_PADDING), sticky="nsew")
        self.__options_frame.grid_columnconfigure(0, weight=1)

        self.__speaker_compas_frame = SpeakerCompasFrame(self, options_frame=self.__options_frame,
                                                         face_tracker=self.__face_tracker,
                                                         corner_radius=CORNER_RADIUS)
        self.__speaker_compas_frame.grid(row=0, column=0, padx=(BORDER_PADDING, BORDER_PADDING / 2),
                                         pady=BORDER_PADDING,
                                         sticky="nsew")

        self.__options_frame.set_speaker_compas_frame(self.__speaker_compas_frame)

        self.protocol("WM_DELETE_WINDOW", self.__on_close)

    def activate_camera_calibration_frame(self):
        self.__face_tracker.reset_rotation_offset()
        self.__speaker_compas_frame.set_camera_calibration(state=True)
        self.__options_frame.grid_forget()
        self.__camera_calibration_frame.set_active_state(state=True)
        self.__camera_calibration_frame.grid(row=0, column=1, padx=(BORDER_PADDING / 2, BORDER_PADDING),
                                             pady=(BORDER_PADDING, BORDER_PADDING), sticky="nsew")

    def activate_options_frame(self):
        self.__camera_calibration_frame.set_active_state(state=False)
        self.__speaker_compas_frame.set_camera_calibration(state=False)
        self.__camera_calibration_frame.grid_forget()
        self.__options_frame.grid(row=0, column=1, padx=(BORDER_PADDING / 2, BORDER_PADDING),
                                  pady=(BORDER_PADDING, BORDER_PADDING), sticky="nsew")

    def get_speaker_compas_frame_width(self):
        return self.__speaker_compas_frame.winfo_width()

    def center_window(self, x_offset=0, y_offset=0):
        self.update_idletasks()
        window_width = self.winfo_width()
        window_height = self.winfo_height()

        current_x = self.winfo_x()
        current_y = self.winfo_y()

        screen_x = 0
        screen_y = 0
        screen_width = 0
        screen_height = 0
        for monitor in get_monitors():
            if monitor.x <= current_x <= monitor.x + monitor.width and monitor.y <= current_y <= monitor.y + monitor.height:
                screen_width = monitor.width
                screen_height = monitor.height
                screen_x = monitor.x
                screen_y = monitor.y
                break

        x_position = screen_x + (screen_width - window_width - x_offset) // 2
        y_position = screen_y + (screen_height - window_height - y_offset) // 2

        self.geometry(f"+{x_position}+{y_position}")

    def get_selected_surround_system(self):
        return self.__selected_surround_system

    def get_speakers_parameters(self):
        return self.__speakers_parameters

    def get_surround_system_dict_sounddevice_order(self):
        return self.__surround_system_dict_sounddevice_order

    def get_default_settings(self):
        return self.__default_settings

    def get_media_name(self):
        return self.__media_name

    def __restore_settings(self):
        if os.path.exists(SAVE_FILE_NAME):
            try:
                with open(SAVE_FILE_NAME, "r", encoding="utf-8") as file:
                    data = json.load(file)
                return data
            except json.JSONDecodeError:
                return self.__default_settings
        else:
            return self.__default_settings

    def __on_close(self):
        offset_rotation_matrix = self.__face_tracker.get_offset_rotation_matrix().tolist()

        self.__options_frame.close_player()
        self.__face_tracker.cleanup()

        data = {
            "media.name": self.__media_name,
            "offset_rotation_matrix": offset_rotation_matrix,
            "selected_surround_system": self.__selected_surround_system.get(),
            "speakers_parameters": self.__speakers_parameters
        }
        with open(SAVE_FILE_NAME, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4)
        print(f"Settings have been saved to: {SAVE_FILE_NAME}.")
        self.destroy()

