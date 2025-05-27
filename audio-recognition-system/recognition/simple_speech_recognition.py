import os
import queue
import threading
import time
from typing import Callable
from google.cloud import speech_v2
from google.api_core.client_options import ClientOptions
from google.protobuf import duration_pb2  # Voice Activity Timeout用

class SimpleStreamingSpeechRecognition:
    """Google Cloud Speech-to-Text V2 + chirp_2の真のストリーミング実装（公式ドキュメント完全準拠）"""
    
    def __init__(self, language_code="ja-JP", result_callback=None, 
                 project_id=None, region="global", verbose=False):
        # 基本設定
        self.language_code = language_code
        self.result_callback = result_callback
        self.verbose = verbose
        
        # 経過時間デバッグ用
        self.start_time = None
        
        # 音声データキュー（ThreadSafeなQueue使用）
        self.audio_queue = queue.Queue()
        
        # ストリーミング制御
        self.streaming_active = False
        self.streaming_start_time = None
        self.max_streaming_duration = 300  # 5分制限
        
        # ログ出力頻度制御（パフォーマンス向上）
        self.last_audio_log_time = 0
        self.last_response_log_time = 0
        self.audio_log_interval = 1.0  # 1秒間隔
        self.response_count = 0
        
        # Google Cloud Speech V2 クライアント初期化
        self.project_id = project_id or os.getenv('GOOGLE_CLOUD_PROJECT')
        self.region = region
        
        if not self.project_id:
            raise ValueError("Google Cloud プロジェクトIDが設定されていません。環境変数GOOGLE_CLOUD_PROJECTを設定してください。")
            
        self.client = speech_v2.SpeechClient()
        
        print(f"🌩️ Simple Google Cloud Speech-to-Text V2 + long 初期化（会議翻訳向けVAD設定）")
        print(f"   プロジェクト: {self.project_id}")
        print(f"   リージョン: {self.region}")
        print(f"   言語: {language_code}")
        print(f"   Voice Activity Detection: 有効（開始10秒待機、終了3秒検出）- テスト用設定")
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
        """ストリーミング認識開始（ブロッキング実行 - 再接続機能対応）"""
        self.streaming_active = True
        self.streaming_start_time = time.time()
        self.start_time = self.streaming_start_time  # 経過時間デバッグ用
        
        print("🌩️ 真のストリーミング認識開始（公式準拠版 + Voice Activity Detection）")
        print(f"⏰ 開始時刻: {time.strftime('%H:%M:%S', time.localtime(self.start_time))}")
        
        # 直接実行（ブロッキング）- 再接続パターンに対応
        self._run_streaming_recognition()
    
    def _get_elapsed_time(self):
        """開始からの経過時間を取得（秒）"""
        if self.start_time:
            return time.time() - self.start_time
        return 0
    
    def _format_elapsed_time(self, elapsed_seconds):
        """経過時間を読みやすい形式でフォーマット"""
        return f"{elapsed_seconds:.1f}秒"
    
    def _audio_generator(self):
        """公式準拠の音声データジェネレーター（継続的ストリーミング）"""
        if self.verbose:
            print("🎵 音声ジェネレーター開始")
        
        while self.streaming_active:
            try:
                # ストリーミング時間制限チェック
                if self.streaming_start_time and (time.time() - self.streaming_start_time) > self.max_streaming_duration:
                    elapsed = self._get_elapsed_time()
                    print(f"⏰ ストリーミング時間制限（5分）に達しました [{self._format_elapsed_time(elapsed)}]")
                    break
                
                # ブロッキング取得でリアルタイム性を確保
                audio_data = self.audio_queue.get(timeout=1.0)
                if audio_data is None:  # 終了シグナル
                    elapsed = self._get_elapsed_time()
                    print(f"🛑 音声ジェネレーター終了シグナル受信 [{self._format_elapsed_time(elapsed)}]")
                    break
                    
                if self.verbose:
                    print(f"🎶 音声データ生成: {len(audio_data)} bytes")
                yield audio_data
                
            except queue.Empty:
                # タイムアウト時は継続（音声がない間も接続維持）
                if self.verbose:
                    print("⏰ 音声待機中...")
                continue
        
        # 終了理由をログ出力
        elapsed = self._get_elapsed_time()
        if not self.streaming_active:
            print(f"🛑 音声ジェネレーター終了: streaming_active=False [{self._format_elapsed_time(elapsed)}]")
        else:
            print(f"🛑 音声ジェネレーター終了: その他の理由 [{self._format_elapsed_time(elapsed)}]")
        
        if self.verbose:
            print("🎵 音声ジェネレーター終了")
    
    def _run_streaming_recognition(self):
        """真のストリーミング認識処理（公式ドキュメント完全準拠 + Voice Activity Detection）"""
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
                model="long",
                features=speech_v2.types.RecognitionFeatures(
                    enable_automatic_punctuation=True,
                    enable_word_time_offsets=True,
                )
            )
            
            # Voice Activity Detection設定（テスト用：10秒でタイムアウト）
            speech_start_timeout = duration_pb2.Duration(seconds=10)  # 10秒でタイムアウト（再接続テスト用）
            speech_end_timeout = duration_pb2.Duration(seconds=3)     # 音声終了から3秒でis_final送信
            voice_activity_timeout = speech_v2.types.StreamingRecognitionFeatures.VoiceActivityTimeout(
                speech_start_timeout=speech_start_timeout,
                speech_end_timeout=speech_end_timeout
            )
            
            streaming_config = speech_v2.types.StreamingRecognitionConfig(
                config=recognition_config,
                streaming_features=speech_v2.types.StreamingRecognitionFeatures(
                    interim_results=True,  # 中間結果も受信
                    enable_voice_activity_events=True,  # Voice Activity Events有効化
                    voice_activity_timeout=voice_activity_timeout  # 音声終了タイムアウト設定
                )
            )
            
            # 公式準拠のリクエスト生成関数
            def generate_requests():
                """公式準拠のリクエストジェネレーター"""
                # 最初のリクエスト（設定のみ）
                print("📤 設定リクエスト送信（Voice Activity Detection有効）")
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
                    
                    # Voice Activity Events処理（Google公式機能）
                    if hasattr(response, 'speech_event_type') and response.speech_event_type:
                        elapsed = self._get_elapsed_time()
                        if response.speech_event_type == speech_v2.types.StreamingRecognizeResponse.SpeechEventType.SPEECH_ACTIVITY_BEGIN:
                            print(f"🗣️ 音声開始検出 [{self._format_elapsed_time(elapsed)}]")
                        elif response.speech_event_type == speech_v2.types.StreamingRecognizeResponse.SpeechEventType.SPEECH_ACTIVITY_END:
                            print(f"🤫 音声終了検出（最終結果送信準備） [{self._format_elapsed_time(elapsed)}]")
                    
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
                                        elapsed = self._get_elapsed_time()
                                        print(f"\n🎯 最終結果: {transcript}")
                                        print(f"   経過時間: [{self._format_elapsed_time(elapsed)}]")
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
                
                # レスポンスストリーム正常終了
                elapsed = self._get_elapsed_time()
                print(f"📨 レスポンスストリーム正常終了 [{self._format_elapsed_time(elapsed)}]")
            
            except Exception as response_error:
                elapsed = self._get_elapsed_time()
                print(f"❌ レスポンス処理中エラー [{self._format_elapsed_time(elapsed)}]: {response_error}")
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
            elapsed = self._get_elapsed_time()
            print(f"🌩️ ストリーミング認識終了 [{self._format_elapsed_time(elapsed)}]")
    
    def stop_recognition(self):
        """認識停止"""
        self.streaming_active = False
        self.audio_queue.put(None)  # 終了シグナル
        print("🛑 認識停止要求送信")
    
    def _reset_for_reconnection(self):
        """再接続用の状態リセット"""
        # キューをクリア（古い音声データを削除）
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        
        # タイムスタンプをリセット
        self.last_audio_log_time = 0
        self.last_response_log_time = 0
        self.response_count = 0
        
        if self.verbose:
            print("🔄 音声認識状態をリセット完了")
    
    def is_active(self):
        """認識がアクティブかどうか"""
        return self.streaming_active 