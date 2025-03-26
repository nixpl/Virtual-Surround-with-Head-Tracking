import numpy as np
import subprocess
import threading
import ctypes
import openal
import time
import math


class VirtualPlayer:
    def __init__(self, pulse, face_tracker, headset_name, media_name, channels_number, speakers_parameters, sink_name, samplerate=44100, dtype=np.int16, buffer_size=1024, buffers_number=5):

        self.__default_device_stimulant_process = subprocess.Popen(["python3", "default_device_stimulant.py"])

        self.__face_tracker = face_tracker
        self.__headset_name = headset_name
        self.__media_name = media_name
        self.__speakers_parameters = speakers_parameters

        self.__previous_data = None

        self.__channels_number = channels_number
        self.__samplerate = samplerate
        self.__dtype = dtype
        self.__buffer_size = buffer_size
        self.__pipe_bufsize = self.__buffer_size * np.dtype(self.__dtype).itemsize * self.__channels_number

        self.__buffers_number = buffers_number


        self.__pulse = pulse
        self.__headset_sink = self.__pulse.get_sink_by_name(self.__headset_name)

        self.__pulse_speaker_name_to_my_dict = {
            "front-left": "Front left",
            "front-right": "Front right",
            "front-center": "Front center",
            "rear-left": "Rear left",
            "rear-right": "Rear right"
        }

        self.__pulse_audio_channel_maps = {
            2: ["front-left", "front-right"],
            3: ["front-left", "front-right", "front-center"],
            5: ["front-left", "front-right", "front-center", "rear-left", "rear-right"]
        }

        self.__pulse_channel_order_list = [self.__pulse_speaker_name_to_my_dict.get(speaker_name) for speaker_name in self.__pulse_audio_channel_maps.get(self.__channels_number)]
        self.__oal_device = None
        self.__oal_context = None
        self.__oal_virtual_speakers = None
        self.__oal_buffers = None
        self.__init_openal()

        self.__sink_name = sink_name
        self.__process = None
        self.__module_id = None
        self.__create_virtual_device()

        self.__listener_orientation = np.array([
                                        np.array([1.0, 0.0, 0.0]),
                                        np.array([0.0, -1.0, 0.0]),
                                        np.array([0.0, 0.0, -1.0])])


        self.__stop_event = threading.Event()

        self.__orientation_thread = threading.Thread(target=self.__update_listener_and_speakers, daemon=True)
        self.__orientation_thread.start()

        self.__play_sound_thread = threading.Thread(target=self.__play_sound, daemon=True)

    def __get_speaker_position(self, speaker_name, distance):
        angle = self.__speakers_parameters.get(speaker_name).get("angle")
        x = distance * math.sin(math.radians(angle))
        y = 0.0
        z = - distance * math.cos(math.radians(angle))
        return x, y, z

    def __init_openal(self):
        # I don't know why but this step helps to switch headset device for OpenAL
        self.__pulse.default_set(self.__headset_sink)


        # OpenAL
        self.__oal_device = openal.alcOpenDevice(None)
        self.__oal_context = openal.alcCreateContext(self.__oal_device, None)
        openal.alcMakeContextCurrent(self.__oal_context)
        openal.alDistanceModel(openal.AL_INVERSE_DISTANCE_CLAMPED)

        listener_position = (ctypes.c_float * 3)(0.0, 0.0, 0.0)
        openal.alListenerfv(openal.AL_POSITION, listener_position)

        self.__oal_virtual_speakers = (openal.ALuint * self.__channels_number)()
        openal.alGenSources(self.__channels_number, self.__oal_virtual_speakers)

        self.__set_speakers_parameters()

        self.__oal_buffers = [(openal.ALuint * self.__buffers_number)() for _ in range(self.__channels_number)]
        for buf in self.__oal_buffers:
            openal.alGenBuffers(self.__buffers_number, buf)

        empty_data = np.zeros(self.__buffer_size, dtype=self.__dtype)
        for buf, speaker in zip(self.__oal_buffers, self.__oal_virtual_speakers):
            for i in range(self.__buffers_number):
                openal.alBufferData(buf[i], openal.AL_FORMAT_MONO16, empty_data.tobytes(), empty_data.nbytes, self.__samplerate)

            openal.alSourceQueueBuffers(speaker, self.__buffers_number, buf)

    def __create_virtual_device(self):
        self.__module_id = self.__pulse.module_load("module-null-sink",
                                                    f"sink_name={self.__sink_name} sink_properties=device.description={self.__sink_name} "
                                                    f"channels={self.__channels_number} "
                                                    f"channel_map={','.join(self.__pulse_audio_channel_maps.get(self.__channels_number))} "
                                                    f"rate={self.__samplerate} ")


        virtual_device_sink = self.__pulse.get_sink_by_name(self.__sink_name)
        self.__pulse.default_set(virtual_device_sink)

        time.sleep(0.1)
        target_property = 'media.name'
        for sink_input in self.__pulse.sink_input_list():
            if target_property in sink_input.proplist and sink_input.proplist[target_property] == self.__media_name:
                command = ['pactl', 'move-sink-input', str(sink_input.index), self.__headset_name]
                subprocess.run(command)

        volume_for_virtual_device = self.__headset_sink.volume.value_flat
        self.__pulse.volume_set_all_chans(virtual_device_sink,volume_for_virtual_device)

        self.__pulse.volume_set_all_chans(self.__headset_sink, 1.0)

        monitor_source_name = f"{self.__sink_name}.monitor"
        command = ["parec", "--latency-msec=1", "-d", f"{monitor_source_name}", f"--channels={self.__channels_number} --rate={self.__samplerate}"]
        self.__process = subprocess.Popen(command, stdout=subprocess.PIPE, bufsize=self.__pipe_bufsize)

    def __update_listener_and_speakers(self, seconds_before_recenter=10):
        while not self.__stop_event.is_set():
            # Listener
            self.__face_tracker.calculate_current_orientation()
            rotation_matrix_opencv = self.__face_tracker.get_current_orientation()

            self.__listener_orientation[0] = rotation_matrix_opencv[0]
            self.__listener_orientation[1] = -rotation_matrix_opencv[1]
            self.__listener_orientation[2] = rotation_matrix_opencv[2]

            combined_vec = np.concatenate((self.__listener_orientation[2], self.__listener_orientation[1]))
            openal.alListenerfv(openal.AL_ORIENTATION, (ctypes.c_float * 6)(*combined_vec))

            # Speakers
            self.__set_speakers_parameters()

            time.sleep(0.01)

    def __set_speakers_parameters(self, distance = 1.0):
        for i, speaker_name in enumerate(self.__pulse_channel_order_list):
            speaker_volume = ctypes.c_float(self.__speakers_parameters.get(speaker_name).get("volume") / 100)
            openal.alSourcefv(self.__oal_virtual_speakers[i], openal.AL_GAIN, speaker_volume)

            speaker_position = (ctypes.c_float * 3)(*self.__get_speaker_position(speaker_name, distance))
            openal.alSourcefv(self.__oal_virtual_speakers[i], openal.AL_POSITION, speaker_position)

    def get_listener_orientation(self):
        return self.__listener_orientation

    def start_playing(self):
        self.__play_sound_thread.start()

    def __play_sound(self):
        for speaker in self.__oal_virtual_speakers:
            openal.alSourcePlay(speaker)

        # Main loop
        while not self.__stop_event.is_set():
            data = self.__process.stdout.read(self.__pipe_bufsize)
            if not self.__handle_playing(data):
                break

        self.__process.terminate()
        self.__process.wait()

    def __handle_playing(self, data):
        if not data:
            return False

        if data == self.__previous_data:
            return True

        self.__previous_data = data

        samples = np.frombuffer(data, dtype=self.__dtype)
        channels = len(self.__oal_virtual_speakers)
        channels_data = [samples[i::channels] for i in range(channels)]

        for i, (speaker, channel_data) in enumerate(zip(self.__oal_virtual_speakers, channels_data)):
            processed = openal.ALint()
            openal.alGetSourcei(speaker, openal.AL_BUFFERS_PROCESSED, processed)
            if processed.value > 0:
                buf_to_refill = openal.ALuint()
                openal.alSourceUnqueueBuffers(speaker, 1, buf_to_refill)

                openal.alBufferData(buf_to_refill, openal.AL_FORMAT_MONO16, channel_data.tobytes(), channel_data.nbytes,
                                    self.__samplerate)
                openal.alSourceQueueBuffers(speaker, 1, buf_to_refill)

            # Sometimes SourcePlayer needs to be restarted
            state = openal.ALint()
            openal.alGetSourcei(speaker, openal.AL_SOURCE_STATE, state)
            if state.value not in [openal.AL_PLAYING, openal.AL_PAUSED]:
                openal.alSourcePlay(speaker)

        return True


    def stop(self):
        self.__stop_event.set()

        self.__play_sound_thread.join()
        self.__orientation_thread.join()
        self.__pulse.volume_set_all_chans(self.__headset_sink, self.__pulse.get_sink_by_name(self.__sink_name).volume.value_flat)
        self.__pulse.default_set(self.__pulse.get_sink_by_name(self.__headset_name))
        self.__process.terminate()
        self.__default_device_stimulant_process.terminate()
        openal.alDeleteSources(self.__channels_number, (openal.ALuint * self.__channels_number)(*self.__oal_virtual_speakers))
        for buf in self.__oal_buffers:
            openal.alDeleteBuffers(self.__buffers_number, buf)
        openal.alcDestroyContext(self.__oal_context)
        openal.alcCloseDevice(self.__oal_device)
        self.__pulse.module_unload(self.__module_id)


























