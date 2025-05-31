#!/usr/bin/env python3
"""
シンプル版 リアルタイム音声認識・翻訳・Google Docs出力システム
StreamingRecognize前提で設計された軽量実装
無音自動一時停止機能付き
"""

# urllib3のNotOpenSSLWarning警告を非表示にする
import os
os.environ['PYTHONWARNINGS'] = 'ignore:urllib3 v2 only supports OpenSSL'

import warnings
warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="urllib3")

try:
    import urllib3
    urllib3.disable_warnings()
except ImportError:
    pass

import sys
import os
import argparse
import threading
import time
import queue
from datetime import datetime
import signal
from enum import Enum
import uuid

# シンプル実装
from audio.simple_capture import SimpleAudioCapture
from recognition.speech_recognition import SimpleStreamingSpeechRecognition

# 既存システムを再利用
sys.path.append(os.path.join(os.path.dirname(__file__), 'config'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'translation'))  
sys.path.append(os.path.join(os.path.dirname(__file__), 'output'))
from mvp_config import MVPConfig, create_mvp_config_from_args
from translator import ClaudeTranslator, TranslationResult
from basic_google_docs_writer import BasicGoogleDocsWriter, MeetingEntry

class SystemState(Enum):
    """システム状態"""
    ACTIVE = "active"           # 通常動作
    PAUSED = "paused"          # 一時停止
    WAITING_INPUT = "waiting"   # キーボード入力待機
    AUTHENTICATING = "authenticating"  # 認証処理中
    SHUTTING_DOWN = "shutdown"  # 終了処理中

class PauseReason(Enum):
    """一時停止理由"""
    SILENCE = "silence"         # 無音による一時停止
    RUNTIME = "runtime"         # 実行時間による一時停止

class SimpleAudioRecognitionSystem:
    """シンプル版音声認識・翻訳・Google Docs出力システム"""
    
    def __init__(self, mvp_config: MVPConfig):
        self.mvp_config = mvp_config
        self.is_running = threading.Event()
        self.is_running.set()
        
        # 無音自動一時停止機能の設定
        self.system_state = SystemState.ACTIVE
        self.state_lock = threading.Lock()
        self.last_speech_time = None
        self.program_start_time = None
        
        # デバッグモード時はタイムアウトを短縮
        if mvp_config.debug or mvp_config.verbose:
            self.SILENCE_TIMEOUT = 30   # デバッグモード: 30秒無音で一時停止
            self.MAX_RUNTIME = 60       # デバッグモード: 60秒（1分）で強制一時停止
            # print("🐛 デバッグモード: タイムアウト時間を短縮（無音30秒、実行1分）")
        else:
            self.SILENCE_TIMEOUT = 300  # 300秒（5分）無音で一時停止
            self.MAX_RUNTIME = 3600     # 3600秒（60分）で強制一時停止
        
        # 音声認識結果を処理するキュー（1つだけ！）
        self.result_queue = queue.Queue()
        
        # プレースホルダー管理
        self.active_placeholders = {}  # {placeholder_id: timestamp}
        self.current_placeholder_id = None  # 現在の音声認識セッション用のプレースホルダーID
        
        # 音声認識結果のコールバック関数（表示は音声認識システム側に任せる）
        def recognition_callback(transcript, confidence, is_final):
            if transcript.strip():
                if not is_final:
                    # 途中結果でプレースホルダーを挿入（最初の途中結果のみ）
                    if self.current_placeholder_id is None:
                        placeholder_id = str(uuid.uuid4())[:8]  # 短縮ID
                        placeholder_timestamp = time.time()  # プレースホルダー挿入時のタイムスタンプを保存
                        if self.docs_writer and not self.mvp_config.disable_docs_output:
                            self.docs_writer.insert_placeholder(self.mvp_config.speaker_name, placeholder_id)
                            # タイムスタンプも保存
                            self.active_placeholders[placeholder_id] = placeholder_timestamp
                            self.current_placeholder_id = placeholder_id
                            # print(f"📝 Placeholder inserted / プレースホルダー挿入: {placeholder_id}")
                else:
                    # 最終結果を翻訳処理用キューに追加
                    self.result_queue.put((transcript, self.current_placeholder_id))
                    # print(f"🎯 最終結果とプレースホルダーID: {self.current_placeholder_id}")
                    
                    # 現在のプレースホルダーIDをリセット（次の音声認識用）
                    self.current_placeholder_id = None
                    
                    # 音声が検出されたので無音タイマーをリセット
                    self.last_speech_time = time.time()
            # 途中結果の表示も音声認識システム側に任せる
        
        # Google Cloud Speech設定
        project_id = os.getenv('GOOGLE_CLOUD_PROJECT') or 'meet-live-transcript'
        region = 'global'
        
        # 音声認識初期化（認証状態コールバック付き）
        self.speech_recognition = SimpleStreamingSpeechRecognition(
            language_code=self._get_language_code(mvp_config.source_lang),
            result_callback=recognition_callback,
            project_id=project_id,
            region=region,
            verbose=mvp_config.verbose,
            auth_state_callback=self._auth_state_callback  # 認証状態変更通知
        )
        
        # シンプル音声キャプチャ（直接認識システムに送信）
        # Google推奨: 100ms chunk @ 16kHz = 1600 samples
        chunk_size = int(mvp_config.sample_rate * 0.1)  # 100ms
        self.audio_capture = SimpleAudioCapture(
            callback_func=self.speech_recognition.add_audio_data,
            input_device=mvp_config.input_device,
            sample_rate=mvp_config.sample_rate,
            chunk_size=chunk_size,
            verbose=mvp_config.verbose
        )
        
        # 翻訳システム（既存再利用）
        self.translator = None
        if not mvp_config.disable_translation:
            self.translator = ClaudeTranslator(mvp_config.claude_api_key, mvp_config.claude_model_name)
            # print(f"✅ 翻訳機能を有効化")
        else:
            print("🚫 翻訳機能を無効化")
        
        # Google Docs出力（既存再利用）
        self.docs_writer = None
        if not mvp_config.disable_docs_output and mvp_config.google_docs_id:
            try:
                self.docs_writer = BasicGoogleDocsWriter(
                    mvp_config.google_credentials_path,
                    mvp_config.google_token_path
                )
                self.docs_writer.set_document_id(mvp_config.google_docs_id)
                # print(f"✅ Google Docs出力を有効化")
            except Exception as e:
                print(f"⚠️ Google Docs初期化エラー: {e}")
                self.docs_writer = None
        else:
            print("🚫 Google Docs出力を無効化")
        
        # 音声認識専用モード用のログファイル設定
        if mvp_config.transcription_only:
            current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = mvp_config.output_dir or "logs"
            os.makedirs(output_dir, exist_ok=True)
            self.transcription_log_path = os.path.join(
                output_dir,
                f"simple_transcription_{mvp_config.source_lang}_{current_time}.txt"
            )
            print(f"📝 ログファイル: {self.transcription_log_path}")
        
        # print("✅ シンプル音声認識システム初期化完了")
    
    def timeout_monitor_thread(self):
        """二重タイマー監視スレッド"""
        # print("🔄 タイムアウト監視スレッド開始")
        
        while self.is_running.is_set():
            try:
                with self.state_lock:
                    if self.system_state == SystemState.SHUTTING_DOWN:
                        # print("🛑 タイムアウト監視スレッド: システム終了により終了")
                        break
                    elif self.system_state != SystemState.ACTIVE:
                        # アクティブでない場合は1秒待機
                        time.sleep(1)
                        continue
                
                current_time = time.time()
                
                # 実行時間チェック（デバッグモードでは60秒、通常は30分）
                if self.program_start_time and current_time - self.program_start_time > self.MAX_RUNTIME:
                    print(f"⏰ 実行時間制限到達: {self.MAX_RUNTIME}秒経過")
                    self._trigger_auto_pause(PauseReason.RUNTIME)
                    return
                
                # 無音時間チェック（デバッグモードでは30秒、通常は5分）
                if self.last_speech_time and current_time - self.last_speech_time > self.SILENCE_TIMEOUT:
                    print(f"🔇 無音時間制限到達: {self.SILENCE_TIMEOUT}秒経過")
                    self._trigger_auto_pause(PauseReason.SILENCE)
                    return
                    
                time.sleep(5)  # 5秒間隔でチェック（より細かく監視）
                
            except Exception as e:
                print(f"❌ タイムアウト監視エラー: {e}")
                time.sleep(2)
        
        # print("🏁 タイムアウト監視スレッド終了")
    
    def keyboard_monitor_thread(self):
        """キーボード入力監視スレッド（ストリーミング中のq/x停止用）"""
        # print("⌨️ キーボード監視スレッド開始")
        
        while self.is_running.is_set():
            try:
                with self.state_lock:
                    if self.system_state == SystemState.SHUTTING_DOWN:
                        # print("🛑 キーボード監視スレッド: システム終了により終了")
                        break
                    elif self.system_state in [SystemState.PAUSED, SystemState.WAITING_INPUT, SystemState.AUTHENTICATING]:
                        # アクティブでない場合や認証中は1秒待機（一時停止中は専用の入力待機を使用）
                        time.sleep(1)
                        continue
                
                # 非ブロッキング入力チェック（stdin.readline()ではなくselect使用）
                import select
                import sys
                
                # 0.5秒タイムアウトで入力をチェック
                if select.select([sys.stdin], [], [], 0.5)[0]:
                    try:
                        user_input = sys.stdin.readline().strip().lower()
                        if user_input in ['q', 'x']:
                            print(f"\n⌨️ キーボード停止コマンド受信: '{user_input}'")
                            print("🛑 ユーザー要求によりシステムを停止します...")
                            self._shutdown_system()
                            return
                        elif user_input:
                            print(f"⌨️ 不明なコマンド: '{user_input}' (q/x で停止)")
                    except:
                        # 入力エラーの場合は無視
                        pass
                        
            except Exception as e:
                # selectが使えない環境への対応
                try:
                    import msvcrt  # Windows用
                    if msvcrt.kbhit():
                        key = msvcrt.getch().decode('utf-8').lower()
                        if key in ['q', 'x']:
                            print(f"\n⌨️ キーボード停止コマンド受信: '{key}'")
                            print("🛑 ユーザー要求によりシステムを停止します...")
                            self._shutdown_system()
                            return
                except ImportError:
                    # selectもmsvcrtも使えない場合は短い間隔で状態チェックのみ
                    time.sleep(0.5)
                    continue
                except Exception:
                    time.sleep(0.5)
                    continue
        
        # print("🏁 キーボード監視スレッド終了")
    
    def _trigger_auto_pause(self, reason: PauseReason):
        """自動一時停止をトリガー"""
        with self.state_lock:
            if self.system_state != SystemState.ACTIVE:
                return
            
            # 先に状態を変更してスレッドの動作を停止
            self.system_state = SystemState.PAUSED
        
        # ログ出力
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if reason == PauseReason.SILENCE:
            message = f"🔔 [{current_time}] ⏸️ 自動一時停止：{self.SILENCE_TIMEOUT}秒間音声が検出されませんでした"
            reason_text = f"{self.SILENCE_TIMEOUT}秒間音声が検出されませんでした"
        else:  # PauseReason.RUNTIME
            message = f"🔔 [{current_time}] ⏸️ 自動一時停止：プログラム開始から{self.MAX_RUNTIME//60}分が経過しました"
            reason_text = f"プログラム開始から{self.MAX_RUNTIME//60}分が経過しました"
        
        print(f"\n{message}")
        
        # 音声キャプチャと認識を停止（状態変更後）
        try:
            # print("🛑 音声キャプチャ停止中...")
            self.audio_capture.stop_capture()
            # print("🛑 音声認識停止中...")
            self.speech_recognition.stop_recognition()
            # print("🛑 音声処理停止完了")
        except Exception as e:
            # print(f"⚠️ 音声処理停止エラー: {e}")
            pass
        
        # 少し待機してから入力待機に移行
        time.sleep(1)
        
        # キーボード入力待機
        self._wait_for_user_input(reason_text, current_time)
    
    def _wait_for_user_input(self, reason_text: str, pause_time: str):
        """キーボード入力待機"""
        with self.state_lock:
            self.system_state = SystemState.WAITING_INPUT
        
        # 確実に表示されるよう、出力をフラッシュ
        # print("\n" + "=" * 60, flush=True)
        # print("=== 自動一時停止中 ===", flush=True)
        # print(f"理由: {reason_text}", flush=True)
        # print(f"時刻: {pause_time}", flush=True)
        # print(flush=True)
        # print("利用可能なコマンド:", flush=True)
        # print("  [Enter] : ストリーミング再開", flush=True)
        # print("  [q] または [x] : プログラム終了", flush=True)
        # print("=" * 60, flush=True)
        # print(flush=True)
        
        while True:
            try:
                # システム状態をチェック
                with self.state_lock:
                    if self.system_state == SystemState.SHUTTING_DOWN:
                        print("🛑 システム終了処理中...")
                        return
                
                command = input("コマンドを入力してください: ").strip().lower()
                print(f"📝 入力されたコマンド: '{command}'", flush=True)
                
                if command == '':  # Enter のみ
                    print("▶️ 再開コマンドが選択されました", flush=True)
                    self._resume_system()
                    break
                elif command in ['q', 'x']:
                    print("🛑 終了コマンドが選択されました", flush=True)
                    self._shutdown_system()
                    break
                else:
                    print("❌ 無効なコマンドです。[Enter] (再開) または 'q' (終了) を入力してください。", flush=True)
                    
            except (KeyboardInterrupt, EOFError):
                print("\n⚠️ 強制終了が要求されました。", flush=True)
                self._shutdown_system()
                break
            except Exception as e:
                print(f"❌ 入力エラー: {e}", flush=True)
                # エラーが発生した場合は少し待機
                time.sleep(0.5)
    
    def _resume_system(self):
        """システム再開"""
        with self.state_lock:
            self.system_state = SystemState.ACTIVE
            
            # タイマーリセット
            current_time = time.time()
            self.program_start_time = current_time
            self.last_speech_time = current_time
            
            print("\n" + "=" * 60)
            print("▶️ ユーザー要求により再開（タイマーリセット）")
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # print(f"🔔 [{timestamp}] 🔔 無音タイマー開始（{self.SILENCE_TIMEOUT}秒後に自動一時停止）")
            # print(f"🔔 [{timestamp}] 🔔 実行時間タイマー開始（{self.MAX_RUNTIME//60}分後に自動一時停止）")
            # print("=" * 60)
            
            # 音声キャプチャと認識を再開
            threading.Thread(target=self.audio_capture.start_capture, daemon=True).start()
            threading.Thread(target=self._continuous_speech_recognition_thread, daemon=True).start()
            threading.Thread(target=self.timeout_monitor_thread, daemon=True).start()
    
    def _shutdown_system(self):
        """システム終了"""
        with self.state_lock:
            self.system_state = SystemState.SHUTTING_DOWN
        
        # print("\n🛑 システム終了処理を開始します...")
        self.is_running.clear()
        
        if hasattr(self, 'audio_capture'):
            self.audio_capture.stop_capture()
        if hasattr(self, 'speech_recognition'):
            self.speech_recognition.stop_recognition()
        
        print("🏁 システムを終了しました。")
        sys.exit(0)
    
    def _get_language_code(self, lang):
        """言語コードをGoogle Cloud Speech V2形式に変換"""
        lang_map = {
            'ja': 'ja-JP',
            'en': 'en-US',
            'ko': 'ko-KR',
            'zh': 'cmn-Hans-CN',
            'es': 'es-ES',
            'fr': 'fr-FR',
            'de': 'de-DE'
        }
        return lang_map.get(lang, 'ja-JP')
    
    def result_processing_thread(self):
        """認識結果を処理するスレッド（翻訳・出力）"""
        # print("🔄 結果処理スレッド開始")
        
        while self.is_running.is_set():
            try:
                # 認識結果を取得
                if not self.result_queue.empty():
                    result_data = self.result_queue.get(timeout=1.0)
                    
                    # 新しいタプル形式（transcript, placeholder_id）または従来の文字列形式に対応
                    if isinstance(result_data, tuple):
                        recognition_result, placeholder_id = result_data
                    else:
                        recognition_result = result_data
                        placeholder_id = None
                    
                    if not recognition_result or not recognition_result.strip():
                        continue
                    
                    # 音声認識専用モード
                    if self.mvp_config.transcription_only:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        
                        # コンソール出力
                        print(f"\n[{timestamp}] {self.mvp_config.speaker_name}:")
                        print(f"認識結果({self.mvp_config.source_lang}): {recognition_result}")
                        print("-" * 50)
                        
                        # ファイル出力
                        with open(self.transcription_log_path, "a", encoding="utf-8") as log_file:
                            log_file.write(f"[{timestamp}] {recognition_result}\n")
                        continue
                    
                    # 翻訳機能が無効な場合
                    if self.mvp_config.disable_translation:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        print(f"\n[{timestamp}] {self.mvp_config.speaker_name}:")
                        print(f"認識結果({self.mvp_config.source_lang}): {recognition_result}")
                        print("-" * 50)
                        continue
                    
                    # Claude翻訳実行
                    translation_result = self.translator.translate(
                        recognition_result,
                        self.mvp_config.source_lang,
                        self.mvp_config.target_lang
                    )
                    
                    if translation_result.success:
                        # プレースホルダーのタイムスタンプを取得
                        entry_timestamp = datetime.now()  # デフォルト
                        if placeholder_id and placeholder_id in self.active_placeholders:
                            entry_timestamp = datetime.fromtimestamp(self.active_placeholders[placeholder_id])
                        
                        # Google Docs出力
                        if self.docs_writer:
                            meeting_entry = MeetingEntry(
                                timestamp=entry_timestamp,
                                speaker_name=self.mvp_config.speaker_name,
                                original_text=translation_result.original_text,
                                translated_text=translation_result.translated_text,
                                source_lang=self.mvp_config.source_lang,
                                target_lang=self.mvp_config.target_lang
                            )
                            
                            # プレースホルダーがあれば更新、なければ通常の書き込み
                            if placeholder_id and placeholder_id in self.active_placeholders:
                                if self.docs_writer.update_placeholder(placeholder_id, meeting_entry):
                                    # print(f"📄 Placeholder updated / プレースホルダー更新完了: {placeholder_id}")
                                    # 使用済みプレースホルダーを削除
                                    del self.active_placeholders[placeholder_id]
                                else:
                                    print(f"❌ Placeholder update failed / プレースホルダー更新失敗: {placeholder_id}")
                                    # 失敗時は通常の書き込みにフォールバック
                                    if self.docs_writer.write_meeting_entry(meeting_entry):
                                        print("📄 Fallback write completed / フォールバック書き込み完了")
                            else:
                                # プレースホルダーがない場合は通常の書き込み
                                if self.docs_writer.write_meeting_entry(meeting_entry):
                                    print("📄 Google Docs output completed / Google Docsに出力完了")
                                else:
                                    print("❌ Google Docs output failed / Google Docs出力失敗")
                        
                        # コンソール出力（プレースホルダーのタイムスタンプを使用）
                        self._print_result_with_timestamp(translation_result, entry_timestamp)
                    
                    else:
                        print(f"❌ 翻訳失敗: {translation_result.error_message}")
                        # 翻訳失敗時も出力
                        if self.docs_writer:
                            meeting_entry = MeetingEntry(
                                timestamp=datetime.now(),
                                speaker_name=self.mvp_config.speaker_name,
                                original_text=recognition_result,
                                translated_text=f"[翻訳失敗: {translation_result.error_message}]",
                                source_lang=self.mvp_config.source_lang,
                                target_lang=self.mvp_config.target_lang
                            )
                            self.docs_writer.write_meeting_entry(meeting_entry)
                
                else:
                    time.sleep(0.1)  # CPU使用率軽減
                    
            except queue.Empty:
                continue
            except Exception as e:
                print(f"❌ 結果処理エラー: {e}")
                time.sleep(1.0)
        
        # print("🔄 結果処理スレッド終了")
    
    def _print_result(self, translation_result: TranslationResult):
        """結果をコンソールに出力"""
        timestamp = datetime.fromtimestamp(translation_result.timestamp).strftime("%H:%M:%S")
        print(f"\n[{timestamp}] {self.mvp_config.speaker_name}:")
        print(f"({translation_result.source_lang}): {translation_result.original_text}")
        print(f"({translation_result.target_lang}): {translation_result.translated_text}")
        print("-" * 50)
    
    def _print_result_with_timestamp(self, translation_result: TranslationResult, timestamp: datetime):
        """結果をコンソールに出力（タイムスタンプを使用）"""
        print(f"\n[{timestamp.strftime('%H:%M:%S')}] {self.mvp_config.speaker_name}:")
        print(f"({translation_result.source_lang}): {translation_result.original_text}")
        print(f"({translation_result.target_lang}): {translation_result.translated_text}")
        print("-" * 50)
    
    def run(self):
        """システム実行（再接続機能付き）"""
        # print("🚀 シンプル音声認識システム開始（再接続機能付き、無音自動一時停止機能付き）")
        
        # 設定表示
        self.mvp_config.print_config()
        
        # API接続テストを無効化（起動時間短縮のため）
        # API接続テストは check_environment.py --api-test で実行してください
        # if not self._test_connections():
        #     print("❌ API接続テスト失敗")
        #     return
        
        # タイマー初期化
        current_time = time.time()
        self.program_start_time = current_time
        self.last_speech_time = current_time
        
        # スレッド作成（シンプル！）
        threads = [
            threading.Thread(target=self.audio_capture.start_capture),
            threading.Thread(target=self.result_processing_thread),
            threading.Thread(target=self._continuous_speech_recognition_thread),  # 新しい継続的認識スレッド
            threading.Thread(target=self.timeout_monitor_thread),  # タイムアウト監視スレッド
            threading.Thread(target=self.keyboard_monitor_thread),  # キーボード監視スレッド
        ]
        
        # スレッド開始
        for thread in threads:
            thread.daemon = True  # メインスレッド終了時に自動終了
            thread.start()
        
        # ステータス表示
        if self.mvp_config.transcription_only:
            # print("\n=== シンプル音声認識専用システム稼働中（継続的再接続機能付き） ===")
            # print(f"発話者: {self.mvp_config.speaker_name}")
            # print(f"認識言語: {self.mvp_config.source_lang}")
            # print(f"出力ファイル: {self.transcription_log_path}")
            pass
        else:
            # print("\n=== シンプル音声認識・翻訳・Google Docs出力システム稼働中（継続的再接続機能付き） ===")
            # print(f"発話者: {self.mvp_config.speaker_name}")
            if not self.mvp_config.disable_translation:
                # print(f"翻訳方向: {self.mvp_config.source_lang} → {self.mvp_config.target_lang}")
                pass
            else:
                print(f"認識言語: {self.mvp_config.source_lang} (翻訳無効)")
        
        # print("⚡ 継続的ストリーミング機能: Googleのタイムアウト制限を自動回避")
        
        # デバッグモード表示
        if self.mvp_config.debug or self.mvp_config.verbose:
            print(f"🐛 デバッグモード - 無音自動一時停止: {self.SILENCE_TIMEOUT}秒間無音で一時停止")
            print(f"🐛 デバッグモード - 実行時間制限: {self.MAX_RUNTIME}秒で自動一時停止")
        else:
            # print(f"🔔 無音自動一時停止: {self.SILENCE_TIMEOUT}秒間無音で一時停止")
            # print(f"⏰ 実行時間制限: {self.MAX_RUNTIME//60}分で自動一時停止")
            pass
        
        print("Ctrl+C または 'q'/'x' + Enter で終了")
        
        # タイマー開始ログ
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if self.mvp_config.debug or self.mvp_config.verbose:
            # print(f"🔔 [{timestamp}] 🔔 無音タイマー開始（{self.SILENCE_TIMEOUT}秒後に自動一時停止）")
            # print(f"🔔 [{timestamp}] 🔔 実行時間タイマー開始（{self.MAX_RUNTIME}秒後に自動一時停止）")
            pass
        else:
            # print(f"🔔 [{timestamp}] 🔔 無音タイマー開始（{self.SILENCE_TIMEOUT}秒後に自動一時停止）")
            # print(f"🔔 [{timestamp}] 🔔 実行時間タイマー開始（{self.MAX_RUNTIME//60}分後に自動一時停止）")
            pass
        # print("=" * 60)
        
        try:
            while True:
                with self.state_lock:
                    if self.system_state == SystemState.SHUTTING_DOWN:
                        break
                time.sleep(1)
        except KeyboardInterrupt:
            # print("\n\n👋 ユーザーによる中断要求")
            with self.state_lock:
                self.system_state = SystemState.SHUTTING_DOWN
            self.is_running.clear()
            self.audio_capture.stop_capture()
            self.speech_recognition.stop_recognition()
            time.sleep(2)  # 終了処理待機
        
        # print("🏁 シンプルシステムを終了しました。")
    
    def _continuous_speech_recognition_thread(self):
        """継続的ストリーミング認識スレッド（再接続機能）"""
        # print("🔄 継続的ストリーミング認識スレッド開始")
        reconnection_count = 0
        
        while self.is_running.is_set():
            try:
                # システム状態をチェック
                with self.state_lock:
                    if self.system_state != SystemState.ACTIVE:
                        print(f"⏸️ システム状態: {self.system_state.value} - ストリーミング認識を一時停止")
                        # 一時停止中は1秒待機してから再チェック
                        time.sleep(1)
                        continue
                
                reconnection_count += 1
                current_time = time.strftime('%H:%M:%S', time.localtime())
                
                if reconnection_count == 1:
                    # print(f"🎤 [{current_time}] ストリーミング認識開始（接続 #{reconnection_count}）")
                    pass
                else:
                    # print(f"🔄 [{current_time}] ストリーミング再接続（接続 #{reconnection_count}）")
                    # 再接続前に状態をリセット
                    self.speech_recognition._reset_for_reconnection()
                
                # ストリーミング認識開始（ブロッキング実行）
                self.speech_recognition.start_streaming_recognition()
                
                # ここに到達するのは正常終了時（15.2秒制限など）
                with self.state_lock:
                    if self.system_state == SystemState.ACTIVE and self.is_running.is_set():
                        current_time = time.strftime('%H:%M:%S', time.localtime())
                        # print(f"✅ [{current_time}] ストリーミング正常終了 - 即座に再接続します")
                        continue
                    else:
                        # print(f"🛑 システム状態変更により継続的ストリーミングを終了 (状態: {self.system_state.value})")
                        break
                    
            except Exception as e:
                current_time = time.strftime('%H:%M:%S', time.localtime())
                print(f"❌ [{current_time}] ストリーミング認識エラー: {e}")
                
                with self.state_lock:
                    if self.system_state == SystemState.ACTIVE and self.is_running.is_set():
                        # print("🔄 エラー後も継続 - 即座に再接続を試行します")
                        continue
                    else:
                        # print(f"🛑 システム状態変更のため継続的ストリーミングを終了 (状態: {self.system_state.value})")
                        break
        
        # print("🏁 継続的ストリーミング認識スレッド終了")
    
    def _auth_state_callback(self, state: str):
        """認証状態変更時のコールバック"""
        if state == "start":
            with self.state_lock:
                # print("🔒 認証処理開始 - キーボード監視を一時停止")
                self.system_state = SystemState.AUTHENTICATING
        elif state == "end":
            with self.state_lock:
                # print("🔓 認証処理終了 - システム状態を復旧")
                # 認証前の状態に戻す（通常はACTIVE）
                if self.system_state == SystemState.AUTHENTICATING:
                    self.system_state = SystemState.ACTIVE


def create_argument_parser() -> argparse.ArgumentParser:
    """コマンドライン引数パーサーを作成（既存再利用）"""
    parser = argparse.ArgumentParser(
        description="シンプル版 リアルタイム音声認識・翻訳・Google Docs出力システム"
    )
    
    # 必須引数
    parser.add_argument(
        '--source-lang', 
        required=True,
        choices=['ja', 'en', 'ko', 'zh', 'es', 'fr', 'de'],
        help='発話言語 (ja, en, ko, zh, es, fr, de)'
    )
    parser.add_argument(
        '--target-lang', 
        required=True,
        choices=['ja', 'en', 'ko', 'zh', 'es', 'fr', 'de'],
        help='翻訳先言語 (ja, en, ko, zh, es, fr, de)'
    )
    parser.add_argument(
        '--speaker-name', 
        required=True,
        help='発話者名'
    )
    
    # オプション引数
    parser.add_argument(
        '--input-device', 
        type=int,
        help='音声入力デバイスのインデックス'
    )
    parser.add_argument(
        '--google-docs-id', 
        help='Google DocsドキュメントID'
    )
    parser.add_argument(
        '--output-dir', 
        help='ログ出力ディレクトリ'
    )
    
    # 機能無効化オプション
    parser.add_argument(
        '--disable-translation',
        action='store_true',
        help='翻訳機能を無効化（音声認識のみ実行）'
    )
    parser.add_argument(
        '--disable-docs-output',
        action='store_true',
        help='Google Docs出力を無効化'
    )
    parser.add_argument(
        '--transcription-only',
        action='store_true',
        help='音声認識のみ実行（翻訳・出力を無効化）'
    )
    
    # 新しいオプション
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='詳細ログを表示'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='デバッグモード（タイムアウト時間短縮: 無音30秒、実行1分）'
    )
    
    return parser


def create_recognition_callback(target_lang, speaker_name, transcription_only):
    """音声認識結果のコールバック関数を作成"""
    
    def on_recognition_result(transcript, confidence, is_final):
        """音声認識結果処理"""
        try:
            if transcript.strip():
                # 結果表示
                status = "🎯 最終" if is_final else "📝 途中"
                # print(f"\n{status}認識結果:")
                # print(f"  発話者: {speaker_name}")
                # print(f"  内容: {transcript}")
                # print(f"  信頼度: {confidence:.2f}")
                
                if transcription_only:
                    # print("  翻訳: スキップ（transcription-onlyモード）")
                    pass
                else:
                    # TODO: 翻訳機能実装
                    # print(f"  翻訳({target_lang}): [翻訳機能未実装]")
                    pass
                # print("-" * 50)
                
        except Exception as e:
            # print(f"⚠️ 認識結果処理エラー: {e}")
            pass
    
    return on_recognition_result


def setup_signal_handlers(audio_capture, speech_recognition):
    """シグナルハンドラー設定"""
    def signal_handler(signum, frame):
        # print(f"\n🛑 終了シグナル受信 (シグナル: {signum})")
        # print("システム終了中...")
        
        # 音声キャプチャ停止
        if audio_capture:
            audio_capture.stop_capture()
        
        # 音声認識停止
        if speech_recognition:
            speech_recognition.stop_recognition()
        
        # 少し待ってから終了
        time.sleep(1)
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)


def main():
    """メイン関数"""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    try:
        # MVP設定作成（既存再利用）
        mvp_config = create_mvp_config_from_args(args)
        
        # 設定検証
        is_valid, errors = mvp_config.validate()
        if not is_valid:
            print("❌ 設定エラー:")
            for error in errors:
                print(f"  - {error}")
            sys.exit(1)
        
        # システム実行
        system = SimpleAudioRecognitionSystem(mvp_config)
        system.run()
        
    except KeyboardInterrupt:
        print("👋 ユーザーによる中断")
    except Exception as e:
        print(f"❌ システムエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 