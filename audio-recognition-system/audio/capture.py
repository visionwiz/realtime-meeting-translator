import pyaudio
import numpy as np
import time

class AudioCapture:
    def __init__(self, config, audio_queue, args):
        self.config = config
        self.audio_queue = audio_queue
        self.args = args

        input_device_index = self.get_input_device_index(self.args.input_device)
        if input_device_index is None:
            raise ValueError("適切な入力デバイスが見つかりません。手動で指定してください。")

        self.input_device_index = input_device_index

    def audio_callback(self, in_data, frame_count, time_info, status):
        audio_data = np.frombuffer(in_data, dtype=self.config.NUMPY_DTYPE)
        self.audio_queue.put(audio_data)
        return (in_data, pyaudio.paContinue)

    def capture_thread(self, is_running):
        audio = pyaudio.PyAudio()

        stream = audio.open(format=self.config.FORMAT,
                            channels=self.config.CHANNELS,
                            rate=self.config.RATE,
                            input=True,
                            input_device_index=self.input_device_index,
                            frames_per_buffer=self.config.CHUNK,
                            stream_callback=self.audio_callback)
        
        print(f"音声キャプチャスレッド開始 (デバイスインデックス: {self.input_device_index})")
        
        stream.start_stream()
        
        while is_running.is_set():
            time.sleep(0.1)
        
        stream.stop_stream()
        stream.close()
        audio.terminate()
        
        print("音声キャプチャスレッド終了")

    @staticmethod
    def get_input_device_index(input_device):
        if input_device is not None:
            return input_device

        # デフォルトでは適切なマイクデバイスを優先選択
        p = pyaudio.PyAudio()
        
        # 1. ヘッドセットマイクを最優先
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if (info["maxInputChannels"] > 0 and 
                ("headset" in info["name"].lower() or 
                 "shokz" in info["name"].lower() or
                 "opencomm" in info["name"].lower())):
                return i
        
        # 2. システムデフォルトデバイス（通常最初のマイク）
        default_device = p.get_default_input_device_info()
        if default_device:
            return default_device["index"]
        
        # 3. 最後の手段：BlackHole等のミキサー
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            if (info["maxInputChannels"] > 0 and
                ("blackhole" in info["name"].lower() or
                 "Stereo Mix" in info["name"].lower() or
                 "ステレオ ミキサー" in info["name"].lower())):
                return i
        
        p.terminate()
        return None
 
