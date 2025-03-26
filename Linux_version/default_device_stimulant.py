import numpy as np
import sounddevice as sd

sample_rate = 44100
duration = 5
silent_sound = np.zeros(int(sample_rate * duration))

def callback(outdata, frames, time, status):
    outdata[:] = np.zeros((frames, 1))

with sd.OutputStream(samplerate=sample_rate, channels=1, callback=callback):
    while True:
        sd.sleep(1000)
