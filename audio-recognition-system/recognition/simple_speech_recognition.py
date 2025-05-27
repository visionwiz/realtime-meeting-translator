import os
import queue
import threading
import time
from typing import Callable
from google.cloud import speech_v2
from google.api_core.client_options import ClientOptions

class SimpleStreamingSpeechRecognition:
    """Google Cloud Speech-to-Text V2 + chirp_2の真のストリーミング実装（公式ドキュメント完全準拠）"""
    
    def __init__(self, language_code="ja-JP", result_callback=None, 
                 project_id=None, region="asia-southeast1", verbose=False):
        # 基本設定
        self.language_code = language_code
        self.result_callback = result_callback
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT", "meeting-voice-bridge")
        self.region = region
        self.verbose = verbose  # 詳細ログ制御
        
        # ログ制御用
        self.last_audio_log_time = 0
        self.last_response_log_time = 0
        self.audio_log_interval = 2.0  # 2秒間隔でログ
        self.response_count = 0
        
        # Google Cloud Speech V2クライアント初期化
        self.client_options = ClientOptions(
            api_endpoint=f"{self.region}-speech.googleapis.com"
        )
        self.client = speech_v2.SpeechClient(client_options=self.client_options)
        
        # ストリーミング管理
        self.audio_queue = queue.Queue()
        self.streaming_active = False
        self.streaming_start_time = None
        self.max_streaming_duration = 300  # 5分制限
        
        print(f"🌩️ Simple Google Cloud Speech-to-Text V2 + chirp_2 初期化（真のストリーミング版）")
        print(f"   プロジェクト: {self.project_id}")
        print(f"   リージョン: {self.region}")
        print(f"   言語: {language_code}")
        if not self.verbose:
            print("   ログモード: 簡潔表示（最終結果のみ表示、詳細ログはverbose=Trueで有効化）")
    
    def add_audio_data(self, audio_data: bytes):
        """音声データをキューに追加"""
        if self.streaming_active:
            self.audio_queue.put(audio_data)
            
            # ログ出力頻度制御（verboseモードのみ詳細表示）
            if self.verbose:
                current_time = time.time()
                if (current_time - self.last_audio_log_time) > self.audio_log_interval:
                    print(f"🎤 音声データ追加: {len(audio_data)} bytes（キューサイズ: {self.audio_queue.qsize()}）")
                    self.last_audio_log_time = current_time
    
    def start_streaming_recognition(self):
        """ストリーミング認識開始"""
        self.streaming_active = True
        self.streaming_start_time = time.time()
        
        # 別スレッドで認識実行
        recognition_thread = threading.Thread(target=self._run_streaming_recognition)
        recognition_thread.daemon = True
        recognition_thread.start()
        
        print("🌩️ 真のストリーミング認識開始（公式準拠版）")
    
    def _audio_generator(self):
        """公式準拠の音声データジェネレーター（継続的ストリーミング）"""
        if self.verbose:
            print("🎵 音声ジェネレーター開始")
        
        while self.streaming_active:
            try:
                # ストリーミング時間制限チェック
                if self.streaming_start_time and (time.time() - self.streaming_start_time) > self.max_streaming_duration:
                    print("⏰ ストリーミング時間制限（5分）に達しました。接続を再開します。")
                    break
                
                # ブロッキング取得でリアルタイム性を確保
                audio_data = self.audio_queue.get(timeout=1.0)
                if audio_data is None:  # 終了シグナル
                    if self.verbose:
                        print("🛑 音声ジェネレーター終了シグナル受信")
                    break
                    
                if self.verbose:
                    print(f"🎶 音声データ生成: {len(audio_data)} bytes")
                yield audio_data
                
            except queue.Empty:
                # タイムアウト時は継続（音声がない間も接続維持）
                if self.verbose:
                    print("⏰ 音声待機中...")
                continue
        
        if self.verbose:
            print("🎵 音声ジェネレーター終了")
    
    def _run_streaming_recognition(self):
        """真のストリーミング認識処理（公式ドキュメント完全準拠）"""
        try:
            # Recognizer リソースパス
            recognizer_name = f"projects/{self.project_id}/locations/{self.region}/recognizers/_"
            if self.verbose:
                print(f"🔧 Recognizer: {recognizer_name}")
            
            # 認識設定（明示的PCMフォーマット指定）
            recognition_config = speech_v2.types.RecognitionConfig(
                explicit_decoding_config=speech_v2.types.ExplicitDecodingConfig(
                    encoding=speech_v2.types.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                    sample_rate_hertz=16000,
                    audio_channel_count=1,
                ),
                language_codes=[self.language_code],
                model="chirp_2",
                features=speech_v2.types.RecognitionFeatures(
                    enable_automatic_punctuation=True,
                    enable_word_time_offsets=True,
                )
            )
            
            streaming_config = speech_v2.types.StreamingRecognitionConfig(
                config=recognition_config,
                streaming_features=speech_v2.types.StreamingRecognitionFeatures(
                    interim_results=True  # 中間結果も受信
                )
            )
            
            # 公式準拠のリクエスト生成関数
            def generate_requests():
                """公式準拠のリクエストジェネレーター"""
                # 最初のリクエスト（設定のみ）
                print("📤 設定リクエスト送信")
                yield speech_v2.types.StreamingRecognizeRequest(
                    recognizer=recognizer_name,
                    streaming_config=streaming_config
                )
                
                # 音声データのリクエスト（継続的）
                print("🎵 音声データストリーミング開始")
                for audio_data in self._audio_generator():
                    if self.verbose:
                        print(f"📤 音声リクエスト送信: {len(audio_data)} bytes")
                    yield speech_v2.types.StreamingRecognizeRequest(
                        audio=audio_data
                    )
                
                if self.verbose:
                    print("📤 リクエストジェネレーター終了")
            
            print("🚀 ストリーミング認識実行開始...")
            
            # ストリーミング認識実行（公式準拠）
            response_stream = self.client.streaming_recognize(
                requests=generate_requests()
            )
            
            print("📨 レスポンス処理開始...")
            self.response_count = 0
            
            try:
                for response in response_stream:
                    self.response_count += 1
                    
                    # レスポンス受信ログ（verboseモードのみ）
                    if self.verbose:
                        current_time = time.time()
                        if (current_time - self.last_response_log_time) > 1.0:
                            print(f"📥 レスポンス受信 #{self.response_count}")
                            self.last_response_log_time = current_time
                    
                    if hasattr(response, 'results') and response.results:
                        for i, result in enumerate(response.results):
                            if self.verbose:
                                print(f"🎯 結果 #{i}: is_final={result.is_final}")
                            
                            if hasattr(result, 'alternatives') and result.alternatives:
                                # 最初の代替結果を使用
                                transcript = result.alternatives[0].transcript
                                confidence = getattr(result.alternatives[0], 'confidence', 0.0)
                                is_final = result.is_final
                                
                                if transcript.strip():
                                    # 最終結果のみ表示（途中結果は非表示）
                                    if is_final:
                                        print(f"\n🎯 最終結果: {transcript}")
                                        if self.verbose:
                                            print(f"   信頼度: {confidence:.2f}")
                                    elif self.verbose:
                                        # verboseモードでのみ途中結果を表示
                                        print(f"📝 途中結果: {transcript}")
                                    
                                    # 結果をコールバック関数に送信（ログ表示はしない）
                                    if self.result_callback:
                                        try:
                                            self.result_callback(transcript, confidence, is_final)
                                        except Exception as callback_error:
                                            print(f"\n❌ コールバック送信エラー: {callback_error}")
                                elif self.verbose:
                                    print("📝 空のtranscript")
                            elif self.verbose:
                                print("📝 alternatives なし")
                    elif self.verbose:
                        print("📭 results なし")
                        # エラー情報があるかチェック
                        if hasattr(response, 'error'):
                            print(f"❌ エラー情報: {response.error}")
            
            except Exception as response_error:
                print(f"❌ レスポンス処理中エラー: {response_error}")
                if self.verbose:
                    import traceback
                    traceback.print_exc()
                            
        except Exception as e:
            print(f"⚠️ ストリーミング認識エラー: {e}")
            if self.verbose:
                import traceback
                traceback.print_exc()
        finally:
            self.streaming_active = False
            print("🌩️ ストリーミング認識終了")
    
    def stop_recognition(self):
        """認識停止"""
        self.streaming_active = False
        self.audio_queue.put(None)  # 終了シグナル
        print("🛑 認識停止要求送信")
    
    def is_active(self):
        """認識がアクティブかどうか"""
        return self.streaming_active 