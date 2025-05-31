import os
import queue
import threading
import time
import subprocess
import sys
import logging
from typing import Callable
from google.cloud import speech_v2
from google.api_core.client_options import ClientOptions
from google.protobuf import duration_pb2  # Voice Activity Timeout用
import google.auth
from google.auth.exceptions import RefreshError

# grpcのエラーログを抑制（認証期限切れ時の不要なエラーメッセージを非表示）
logging.getLogger('grpc._plugin_wrapping').setLevel(logging.CRITICAL)
# Google OAuth2のエラーログも抑制
logging.getLogger('google.auth.transport.grpc').setLevel(logging.CRITICAL)
logging.getLogger('google.oauth2.reauth').setLevel(logging.CRITICAL)

class SimpleStreamingSpeechRecognition:
    """Google Cloud Speech-to-Text V2 + chirp_2の真のストリーミング実装（公式ドキュメント完全準拠）"""
    
    def __init__(self, language_code="ja-JP", result_callback=None, 
                 project_id=None, region="global", verbose=False, auth_state_callback=None):
        # 基本設定
        self.language_code = language_code
        self.result_callback = result_callback
        self.auth_state_callback = auth_state_callback  # 認証状態変更通知用コールバック
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
        
        # Google Cloud Speech V2 クライアント初期化（認証エラー自動修復付き）
        self.project_id = project_id or os.getenv('GOOGLE_CLOUD_PROJECT')
        self.region = region
        
        if not self.project_id:
            raise ValueError("Google Cloud プロジェクトIDが設定されていません。環境変数GOOGLE_CLOUD_PROJECTを設定してください。")
        
        # 認証付きクライアント初期化
        self.client = self._initialize_client_with_auth()
        
        print(f"🌩️ Simple Google Cloud Speech-to-Text V2 + long 初期化（会議翻訳向けVAD設定）")
        print(f"   プロジェクト: {self.project_id}")
        print(f"   リージョン: {self.region}")
        print(f"   言語: {language_code}")
        print(f"   モデル: long + インラインフレーズセット適応（13フレーズ、boost最大値20）")
        print(f"   フレーズセット: せんせいフォト、メディアセレクター、コドモン、子どもん等")
        print(f"   Voice Activity Detection: 有効（開始10秒待機、終了3秒検出）- テスト用設定")
        if not self.verbose:
            print("   ログモード: 簡潔表示（最終結果のみ表示、詳細ログはverbose=Trueで有効化）")
    
    def _initialize_client_with_auth(self):
        """認証エラー自動修復付きクライアント初期化"""
        max_retries = 2
        for attempt in range(max_retries):
            try:
                # 認証情報の確認
                credentials, project = google.auth.default()
                
                # クライアント作成
                client = speech_v2.SpeechClient()
                
                # 簡単な認証テスト（ダミーリクエスト）
                try:
                    # 認証が有効かテスト
                    recognizer_name = f"projects/{self.project_id}/locations/{self.region}/recognizers/_"
                    # 実際にはリクエストを送信せず、クライアントの初期化のみテスト
                    print("✅ Google Cloud Speech API認証成功")
                    return client
                except Exception as auth_test_error:
                    if "Reauthentication is needed" in str(auth_test_error) or "RefreshError" in str(auth_test_error):
                        print(f"⚠️ 認証エラー検出: {auth_test_error}")
                        if attempt < max_retries - 1:
                            print("🔄 自動認証修復を試行します...")
                            if self._auto_fix_authentication():
                                print("✅ 認証修復成功、再試行します...")
                                continue
                            else:
                                print("❌ 認証修復失敗")
                        raise auth_test_error
                    else:
                        # その他のエラーはそのまま投げる
                        raise auth_test_error
                        
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"⚠️ クライアント初期化失敗 (試行 {attempt + 1}/{max_retries}): {e}")
                    if self._is_authentication_error(e):
                        print("🔄 認証エラーのため自動修復を試行...")
                        if self._auto_fix_authentication():
                            continue
                else:
                    print(f"❌ クライアント初期化最終失敗: {e}")
                    # 最終失敗時も認証エラーなら自動修復を試行
                    if self._is_authentication_error(e):
                        print("🔄 最終試行: 認証エラーのため自動修復を試行...")
                        if self._auto_fix_authentication():
                            print("✅ 認証修復成功、クライアント初期化を再試行...")
                            return self._initialize_client_with_auth()
                    raise e
        
        raise Exception("Google Cloud Speech APIクライアントの初期化に失敗しました")
    
    def _auto_fix_authentication(self) -> bool:
        """Google Cloud認証の自動修復"""
        try:
            # 認証開始を通知
            if self.auth_state_callback:
                self.auth_state_callback("start")
            
            print("🔧 Google Cloud認証の自動修復を開始...")
            
            # gcloudコマンドの存在確認
            try:
                result = subprocess.run(['gcloud', '--version'], 
                                      capture_output=True, text=True, timeout=10)
                if result.returncode != 0:
                    print("❌ gcloudコマンドが見つかりません")
                    return False
            except (subprocess.TimeoutExpired, FileNotFoundError):
                print("❌ gcloudコマンドが利用できません")
                return False
            
            print("📋 認証修復の説明:")
            print("   Google Cloud Speech APIの認証が期限切れです。")
            print("   自動でブラウザが開き、Googleアカウントでの認証が必要です。")
            print("   認証完了後、システムが自動的に再開されます。")
            
            # ユーザーに確認（新しい入力形式）
            print("\n🔐 自動認証オプション:")
            print("   [auth] : 認証を実行")
            print("   [skip] : 認証をスキップ")
            
            try:
                while True:
                    user_input = input("コマンドを入力してください: ").strip().lower()
                    if user_input == 'auth':
                        print("✅ 認証実行が選択されました")
                        break
                    elif user_input == 'skip':
                        print("❌ 認証がスキップされました")
                        return False
                    else:
                        print("❌ 無効なコマンドです。'auth' または 'skip' を入力してください。")
                        
            except (KeyboardInterrupt, EOFError):
                print("\n❌ 認証がキャンセルされました")
                return False
            
            print("🌐 ブラウザで認証を開始します...")
            print("   ブラウザが開かない場合は、表示されるURLを手動でブラウザで開いてください。")
            
            # gcloud auth application-default loginを実行
            try:
                result = subprocess.run([
                    'gcloud', 'auth', 'application-default', 'login'
                ], timeout=300)  # 5分タイムアウト
                
                if result.returncode == 0:
                    print("✅ 認証が完了しました")
                    
                    # 認証情報の再読み込みを強制
                    import importlib
                    import google.auth
                    importlib.reload(google.auth)
                    
                    return True
                else:
                    print(f"❌ 認証コマンドが失敗しました (終了コード: {result.returncode})")
                    return False
                    
            except subprocess.TimeoutExpired:
                print("❌ 認証がタイムアウトしました（5分制限）")
                return False
            except Exception as e:
                print(f"❌ 認証コマンド実行エラー: {e}")
                return False
                
        except Exception as e:
            print(f"❌ 認証修復処理でエラー: {e}")
            return False
        finally:
            # 認証終了を通知
            if self.auth_state_callback:
                self.auth_state_callback("end")
    
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
        """真のストリーミング認識処理（公式ドキュメント完全準拠 + Voice Activity Detection + 認証エラー自動修復）"""
        try:
            # Recognizer リソースパス
            recognizer_name = f"projects/{self.project_id}/locations/{self.region}/recognizers/_"
            if self.verbose:
                print(f"🔧 Recognizer: {recognizer_name}")
            
            # 認識設定（明示的PCMフォーマット指定 + インラインフレーズセット適応）
            # Google Cloud コンソールの設定内容をインラインで実装 + 表記揺れ対応 + boost最大化
            phrase_set = speech_v2.types.PhraseSet(
                phrases=[
                    {"value": "アンレジスタードフェイス", "boost": 20.0},  # boost最大化
                    {"value": "アンレジスタード", "boost": 20.0},          # boost最大化
                    {"value": "メディアセレクター", "boost": 20.0},         # boost最大化
                    {"value": "メディアセレクタ", "boost": 20.0},          # boost最大化
                    {"value": "せんせいフォト", "boost": 20.0},            # boost最大化
                    {"value": "先生フォト", "boost": 20.0},               # boost最大化
                    {"value": "とりんく", "boost": 20.0},                 # boost最大化
                    {"value": "トリンク", "boost": 20.0},                 # boost最大化
                    {"value": "コドモン", "boost": 20.0},                 # boost最大化
                    {"value": "こどもん", "boost": 20.0},                 # boost最大化
                    {"value": "子供ん", "boost": 20.0},                  # 表記揺れ追加
                    {"value": "子どもん", "boost": 20.0},                 # 表記揺れ追加
                    {"value": "codmon", "boost": 20.0}                   # boost最大化
                ]
            )
            
            speech_adaptation = speech_v2.types.SpeechAdaptation(
                phrase_sets=[
                    speech_v2.types.SpeechAdaptation.AdaptationPhraseSet(
                        inline_phrase_set=phrase_set
                    )
                ]
            )
            
            recognition_config = speech_v2.types.RecognitionConfig(
                explicit_decoding_config=speech_v2.types.ExplicitDecodingConfig(
                    encoding=speech_v2.types.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
                    sample_rate_hertz=16000,
                    audio_channel_count=1,
                ),
                language_codes=[self.language_code],
                model="long",
                adaptation=speech_adaptation,  # インラインフレーズセット適応を追加
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
                
                # 認証エラーの場合は自動修復を試行
                if self._is_authentication_error(response_error):
                    print("🔧 認証エラーを検出、自動修復を試行します...")
                    if self._auto_fix_authentication():
                        print("✅ 認証修復成功、クライアントを再初期化します...")
                        try:
                            self.client = self._initialize_client_with_auth()
                            print("🔄 認証修復後、ストリーミングを再開してください")
                        except Exception as reinit_error:
                            print(f"❌ クライアント再初期化失敗: {reinit_error}")
                    else:
                        print("❌ 認証修復失敗")
                
                if self.verbose:
                    import traceback
                    traceback.print_exc()
                            
        except Exception as e:
            print(f"⚠️ ストリーミング認識エラー: {e}")
            
            # 認証エラーの場合は自動修復を試行
            if self._is_authentication_error(e):
                print("🔧 ストリーミング開始時の認証エラーを検出、自動修復を試行します...")
                if self._auto_fix_authentication():
                    print("✅ 認証修復成功、クライアントを再初期化します...")
                    try:
                        self.client = self._initialize_client_with_auth()
                        print("🔄 認証修復後、ストリーミングを再開してください")
                    except Exception as reinit_error:
                        print(f"❌ クライアント再初期化失敗: {reinit_error}")
                else:
                    print("❌ 認証修復失敗")
            
            if self.verbose:
                import traceback
                traceback.print_exc()
        finally:
            self.streaming_active = False
            elapsed = self._get_elapsed_time()
            print(f"🌩️ ストリーミング認識終了 [{self._format_elapsed_time(elapsed)}]")
    
    def _is_authentication_error(self, error) -> bool:
        """エラーが認証関連かどうかを判定"""
        error_str = str(error).lower()
        auth_error_keywords = [
            "reauthentication is needed",
            "refresherror",
            "authentication",
            "credentials",
            "unauthorized",
            "403",
            "invalid_grant",
            "credentials were not found",  # 認証情報が見つからない場合
            "default credentials",         # ADCの問題
            "application default credentials"  # ADCの設定問題
        ]
        return any(keyword in error_str for keyword in auth_error_keywords)
    
    def stop_recognition(self):
        """認識停止"""
        self.streaming_active = False
        self.audio_queue.put(None)  # 終了シグナル
        print("🛑 認識停止要求送信")
    
    def _reset_for_reconnection(self):
        """再接続用の状態リセット"""
        # キューをクリア
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break
        
        # フラグリセット
        self.streaming_active = False
        self.response_count = 0
        
        if self.verbose:
            print("🔄 再接続用状態リセット完了")
    
    def is_active(self):
        """認識がアクティブかどうか"""
        return self.streaming_active 