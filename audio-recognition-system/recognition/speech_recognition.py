import sys
import os
import datetime
import queue
import wave
import time
import numpy as np
import pyaudio
from language_config import LanguageConfig
import io
import threading
from concurrent.futures import ThreadPoolExecutor

# Google Cloud Speech-to-Text V2関連
from google.cloud import speech_v2
from google.api_core.client_options import ClientOptions
import google.auth
from google.auth.transport.requests import Request


class GoogleCloudSpeechV2Recognition:
    """Google Cloud Speech-to-Text API V2 + chirp_2を使用する音声認識クラス"""
    
    def __init__(self, config, processing_queue, translation_queue, args, lang_config):
        self.config = config
        self.processing_queue = processing_queue
        self.translation_queue = translation_queue
        self.args = args
        self.lang_config = lang_config
        
        # プロジェクト設定
        self.project_id = os.getenv("GOOGLE_CLOUD_PROJECT", "meeting-voice-bridge")
        self.region = "asia-southeast1"
        
        # Google Cloud Speech V2クライアント初期化
        self.client_options = ClientOptions(
            api_endpoint=f"{self.region}-speech.googleapis.com"
        )
        self.client = speech_v2.SpeechClient(client_options=self.client_options)
        
        # ストリーミング用キューとフラグ
        self.streaming_queue = queue.Queue()
        self.streaming_active = False
        
        print(f"🌩️ Google Cloud Speech-to-Text V2 + chirp_2 初期化完了")
        print(f"   リージョン: {self.region}")
        print(f"   言語: {lang_config.get_source_language_code()}")
        print(f"   プロジェクト: {self.project_id}")
    
    def run_recognition_thread(self):
        """音声認識メインスレッド"""
        try:
            # Streamingでchirp_2を使用
            self._run_streaming_recognition()
        except Exception as e:
            print(f"⚠️ 音声認識エラー: {e}")
            # フォールバック: 標準モデルを使用
            self._run_standard_recognition()
    
    def _run_streaming_recognition(self):
        """Google Cloud Speech V2 + chirp_2 ストリーミング認識"""
        print("🌩️ Google Cloud Speech-to-Text V2 ストリーミング開始")
        
        # Recognizer リソースパス
        recognizer_name = f"projects/{self.project_id}/locations/{self.region}/recognizers/_"
        
        # ストリーミング設定
        streaming_config = speech_v2.types.StreamingRecognitionConfig(
            config=speech_v2.types.RecognitionConfig(
                auto_decoding_config=speech_v2.types.AutoDetectDecodingConfig(),
                language_codes=[self.lang_config.get_source_language_code()],
                model="chirp_2",
                features=speech_v2.types.RecognitionFeatures(
                    enable_automatic_punctuation=True,
                    enable_word_time_offsets=True,
                )
            ),
            streaming_features=speech_v2.types.StreamingRecognitionFeatures(
                interim_results=True
            )
        )
        
        # 最初のリクエスト（設定のみ）
        def request_generator():
            # 設定リクエスト
            yield speech_v2.types.StreamingRecognizeRequest(
                recognizer=recognizer_name,
                streaming_config=streaming_config
            )
            
            # 音声データリクエスト
            while self.streaming_active:
                try:
                    data = self.streaming_queue.get(timeout=1.0)
                    if data is None:  # 終了シグナル
                        break
                    yield speech_v2.types.StreamingRecognizeRequest(audio=data)
                except queue.Empty:
                    continue
        
        self.streaming_active = True
        
        try:
            # ストリーミング認識実行
            response_stream = self.client.streaming_recognize(request_generator())
            
            for response in response_stream:
                if response.results:
                    result = response.results[0]
                    if result.alternatives:
                        transcript = result.alternatives[0].transcript
                        confidence = getattr(result.alternatives[0], 'confidence', 0.0)
                        is_final = result.is_final
                        
                        if transcript.strip():
                            print(f"🎯 認識結果 ({confidence:.2f}): {transcript}")
                            
                            if is_final:
                                # 最終結果を処理
                                self._process_final_result(transcript, confidence)
                            else:
                                # 中間結果を表示
                                print(f"  📝 途中結果: {transcript}")
                                
        except Exception as e:
            print(f"⚠️ ストリーミング認識エラー: {e}")
            self.streaming_active = False
    
    def _run_standard_recognition(self):
        """標準的な音声認識（フォールバック）"""
        print("💡 標準の認識設定を使用します")
        
        try:
            import speech_recognition as sr
            
            r = sr.Recognizer()
            mic = sr.Microphone(device_index=self.args.input_device)
            
            print("音声認識待機中...")
            
            with mic as source:
                r.adjust_for_ambient_noise(source)
            
            while True:
                try:
                    with mic as source:
                        audio = r.listen(source, timeout=1, phrase_time_limit=10)
                    
                    # Google Speech-to-Textで認識
                    text = r.recognize_google(audio, language=self.lang_config.get_source_language_code())
                    
                    if text.strip():
                        print(f"🎯 認識結果: {text}")
                        self._process_final_result(text, 0.8)
                        
                except sr.WaitTimeoutError:
                    pass
                except sr.UnknownValueError:
                    pass
                except sr.RequestError as e:
                    print(f"⚠️ 認識リクエストエラー: {e}")
                    time.sleep(1)
                except KeyboardInterrupt:
                    break
                    
        except ImportError:
            print("⚠️ SpeechRecognitionライブラリが不足しています")
    
    def _process_final_result(self, transcript, confidence):
        """最終認識結果の処理"""
        current_time = datetime.datetime.now()
        
        # 認識結果をキューに追加
        recognition_data = {
            'timestamp': current_time,
            'text': transcript,
            'confidence': confidence,
            'speaker': self.args.speaker_name,
            'language': self.lang_config.get_source_language()
        }
        
        # 翻訳システムのために、文字列を旧システム形式で送信
        self.translation_queue.put(transcript)
    
    def add_audio_data(self, audio_data):
        """音声データを認識キューに追加"""
        if self.streaming_active:
            self.streaming_queue.put(audio_data)
    
    def stop_recognition(self):
        """音声認識を停止"""
        self.streaming_active = False
        self.streaming_queue.put(None)  # 終了シグナル
        print("🌩️ Google Cloud Speech-to-Text V2 認識停止")

# 既存のSpeechRecognitionクラスを置き換える
SpeechRecognition = GoogleCloudSpeechV2Recognition

