import pyaudio
import numpy as np
import time
import threading
import wave
import io

class SimpleAudioCapture:
    """StreamingRecognize専用のシンプルな音声キャプチャ"""
    
    def __init__(self, callback_func, input_device=None, sample_rate=16000, chunk_size=1600, verbose=False):
        self.callback_func = callback_func
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.input_device = self.get_input_device_index(input_device)
        self.is_running = False
        self.is_paused = False  # 一時停止制御
        self.verbose = verbose  # 詳細ログ制御
        
        # ログ制御用
        self.last_audio_level_log_time = 0
        self.audio_level_log_interval = 3.0  # 3秒間隔でログ
        
        print(f"🎤 シンプル音声キャプチャ初期化")
        print(f"   デバイス: {self.input_device}")
        print(f"   サンプルレート: {sample_rate}Hz")
        print(f"   チャンクサイズ: {chunk_size}")
        if not self.verbose:
            print("   ログモード: 簡潔表示（最終結果のみ表示）")
    
    def get_input_device_index(self, preferred_device):
        """入力デバイスのインデックスを取得"""
        if preferred_device is not None:
            return preferred_device
            
        audio = pyaudio.PyAudio()
        
        # Black Hole 2chを優先的に検索
        for i in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                device_name = info['name'].lower()
                if 'blackhole' in device_name and '2ch' in device_name:
                    audio.terminate()
                    print(f"✅ BlackHole 2ch検出: {info['name']}")
                    return i
        
        # 一般的なBlackHoleを検索
        for i in range(audio.get_device_count()):
            info = audio.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                device_name = info['name'].lower()
                if 'blackhole' in device_name:
                    audio.terminate()
                    print(f"✅ BlackHole検出: {info['name']}")
                    return i
        
        # デフォルト入力デバイスを使用
        default_device = audio.get_default_input_device_info()
        audio.terminate()
        print(f"⚠️ BlackHole未検出。デフォルトデバイス使用: {default_device['name']}")
        return default_device['index']
    
    def start_capture(self):
        """音声キャプチャ開始"""
        self.is_running = True
        
        audio = pyaudio.PyAudio()
        
        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.input_device,
                frames_per_buffer=self.chunk_size
            )
            
            print(f"🎤 音声キャプチャ開始 (デバイス: {self.input_device})")
            
            while self.is_running:
                try:
                    # 音声データを読み取り
                    data = stream.read(self.chunk_size, exception_on_overflow=False)
                    
                    # 一時停止中でなければデータ送信
                    if not self.is_paused:
                        # 生のPCMデータを直接送信（WAV変換なし）
                        self.callback_func(data)
                    
                    # デバッグ用: 音声レベル表示（verboseモードのみ）
                    if self.verbose:
                        try:
                            audio_level = np.frombuffer(data, dtype=np.int16)
                            if len(audio_level) > 0:
                                rms = np.sqrt(np.mean(audio_level.astype(np.float64)**2))
                                
                                current_time = time.time()
                                if not np.isnan(rms) and not np.isinf(rms) and rms > 500:  # 音声検出閾値
                                    if (current_time - self.last_audio_level_log_time) > self.audio_level_log_interval:
                                        print(f"🔊 音声検出: RMS={rms:.0f}, データサイズ={len(data)}bytes")
                                        self.last_audio_level_log_time = current_time
                        except Exception as audio_level_error:
                            print(f"⚠️ 音声レベル計算エラー: {audio_level_error}")
                    
                except Exception as e:
                    if self.is_running:  # 終了処理中でなければエラー表示
                        print(f"⚠️ 音声読み取りエラー: {e}")
                    break
            
        except Exception as e:
            print(f"❌ 音声ストリーム開始エラー: {e}")
        finally:
            try:
                stream.stop_stream()
                stream.close()
            except:
                pass
            audio.terminate()
            print("🎤 音声キャプチャ終了")
    
    def _pcm_to_wav(self, pcm_data):
        """PCMデータをWAVフォーマットに変換"""
        # インメモリWAVファイル作成
        wav_buffer = io.BytesIO()
        
        with wave.open(wav_buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # モノラル
            wav_file.setsampwidth(2)  # 16bit = 2bytes
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(pcm_data)
        
        wav_buffer.seek(0)
        return wav_buffer.read()
    
    def pause_capture(self):
        """音声キャプチャ一時停止（テスト用）"""
        self.is_paused = True
        print("⏸️ 音声キャプチャ一時停止（Voice Activity Detection テスト用）")
    
    def resume_capture(self):
        """音声キャプチャ再開（テスト用）"""
        self.is_paused = False
        print("▶️ 音声キャプチャ再開")
    
    def stop_capture(self):
        """音声キャプチャ停止"""
        self.is_running = False 