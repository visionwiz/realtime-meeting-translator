#!/usr/bin/env python3
"""
シンプル版 リアルタイム音声認識・翻訳・Google Docs出力システム
StreamingRecognize前提で設計された軽量実装
"""

import sys
import os
import argparse
import threading
import time
import queue
from datetime import datetime
import signal

# シンプル実装
from audio.simple_capture import SimpleAudioCapture
from recognition.simple_speech_recognition import SimpleStreamingSpeechRecognition

# 既存システムを再利用
sys.path.append(os.path.join(os.path.dirname(__file__), 'config'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'translation'))  
sys.path.append(os.path.join(os.path.dirname(__file__), 'output'))
from mvp_config import MVPConfig, create_mvp_config_from_args
from claude_translator import ClaudeTranslator, TranslationResult
from basic_google_docs_writer import BasicGoogleDocsWriter, MeetingEntry

class SimpleAudioRecognitionSystem:
    """シンプル版音声認識・翻訳・Google Docs出力システム"""
    
    def __init__(self, mvp_config: MVPConfig):
        self.mvp_config = mvp_config
        self.is_running = threading.Event()
        self.is_running.set()
        
        # 音声認識結果を処理するキュー（1つだけ！）
        self.result_queue = queue.Queue()
        
        # 音声認識結果のコールバック関数（表示は音声認識システム側に任せる）
        def recognition_callback(transcript, confidence, is_final):
            if is_final and transcript.strip():
                # 最終結果のみキューに追加（表示はしない）
                self.result_queue.put(transcript)
            # 途中結果の表示も音声認識システム側に任せる
        
        # シンプル音声認識システム
        self.speech_recognition = SimpleStreamingSpeechRecognition(
            language_code=self._get_language_code(mvp_config.source_lang),
            result_callback=recognition_callback,
            verbose=mvp_config.verbose
        )
        
        # シンプル音声キャプチャ（直接認識システムに送信）
        self.audio_capture = SimpleAudioCapture(
            callback_func=self.speech_recognition.add_audio_data,
            input_device=mvp_config.input_device,
            sample_rate=mvp_config.sample_rate,
            verbose=mvp_config.verbose
        )
        
        # 翻訳システム（既存再利用）
        self.translator = None
        if not mvp_config.disable_translation:
            self.translator = ClaudeTranslator(mvp_config.claude_api_key, mvp_config.claude_model_name)
            print("✅ 翻訳機能を有効化")
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
                print("✅ Google Docs出力を有効化")
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
        
        print("✅ シンプル音声認識システム初期化完了")
    
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
        print("🔄 結果処理スレッド開始")
        
        # セッションヘッダー書き込み
        if self.docs_writer:
            session_info = {
                'speaker_name': self.mvp_config.speaker_name,
                'source_lang': self.mvp_config.source_lang,
                'target_lang': self.mvp_config.target_lang
            }
            self.docs_writer.write_session_header(session_info)
        
        while self.is_running.is_set():
            try:
                # 認識結果を取得
                if not self.result_queue.empty():
                    recognition_result = self.result_queue.get(timeout=1.0)
                    
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
                        # Google Docs出力
                        if self.docs_writer:
                            meeting_entry = MeetingEntry(
                                timestamp=datetime.now(),
                                speaker_name=self.mvp_config.speaker_name,
                                original_text=translation_result.original_text,
                                translated_text=translation_result.translated_text,
                                source_lang=self.mvp_config.source_lang,
                                target_lang=self.mvp_config.target_lang
                            )
                            
                            if self.docs_writer.write_meeting_entry(meeting_entry):
                                print("📄 Google Docsに出力完了")
                            else:
                                print("❌ Google Docs出力失敗")
                        
                        # コンソール出力
                        self._print_result(translation_result)
                    
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
        
        print("🔄 結果処理スレッド終了")
    
    def _print_result(self, translation_result: TranslationResult):
        """結果をコンソールに出力"""
        timestamp = datetime.fromtimestamp(translation_result.timestamp).strftime("%H:%M:%S")
        print(f"\n[{timestamp}] {self.mvp_config.speaker_name}:")
        print(f"原文({translation_result.source_lang}): {translation_result.original_text}")
        print(f"翻訳({translation_result.target_lang}): {translation_result.translated_text}")
        print("-" * 50)
    
    def run(self):
        """システム実行"""
        print("🚀 シンプル音声認識システム開始")
        
        # 設定表示
        self.mvp_config.print_config()
        
        # API接続テスト
        if not self._test_connections():
            print("❌ API接続テスト失敗")
            return
        
        # スレッド作成（シンプル！）
        threads = [
            threading.Thread(target=self.audio_capture.start_capture),
            threading.Thread(target=self.result_processing_thread),
        ]
        
        # スレッド開始
        for thread in threads:
            thread.daemon = True  # メインスレッド終了時に自動終了
            thread.start()
        
        # 音声認識開始
        self.speech_recognition.start_streaming_recognition()
        
        # ステータス表示
        if self.mvp_config.transcription_only:
            print("\n=== シンプル音声認識専用システム稼働中 ===")
            print(f"発話者: {self.mvp_config.speaker_name}")
            print(f"認識言語: {self.mvp_config.source_lang}")
            print(f"出力ファイル: {self.transcription_log_path}")
        else:
            print("\n=== シンプル音声認識・翻訳・Google Docs出力システム稼働中 ===")
            print(f"発話者: {self.mvp_config.speaker_name}")
            if not self.mvp_config.disable_translation:
                print(f"翻訳方向: {self.mvp_config.source_lang} → {self.mvp_config.target_lang}")
            else:
                print(f"認識言語: {self.mvp_config.source_lang} (翻訳無効)")
        
        print("Ctrl+Cで終了")
        print("=" * 60)
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n終了処理中...")
            self.is_running.clear()
            self.audio_capture.stop_capture()
            self.speech_recognition.stop_recognition()
            time.sleep(2)  # 終了処理待機
        
        print("🏁 シンプルシステムを終了しました。")
    
    def _test_connections(self) -> bool:
        """API接続テスト（既存再利用）"""
        print("🔍 API接続テスト開始")
        
        # Claude翻訳テスト
        if self.translator:
            if not self.translator.test_connection():
                print("❌ Claude API接続テスト失敗")
                return False
            print("✅ Claude API接続成功")
        else:
            print("🚫 Claude翻訳テストをスキップ")
        
        # Google Docs接続テスト
        if self.docs_writer:
            if not self.docs_writer.test_connection():
                print("❌ Google Docs API接続テスト失敗")
                return False
            print("✅ Google Docs API接続成功")
            
            if not self.docs_writer.verify_document_access():
                print("❌ Google Docsドキュメントアクセス確認失敗")
                return False
            print("✅ Google Docsドキュメントアクセス確認成功")
        else:
            print("🚫 Google Docs出力テストをスキップ")
        
        print("✅ API接続テスト完了")
        return True


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
    
    return parser


def create_recognition_callback(target_lang, speaker_name, transcription_only):
    """音声認識結果のコールバック関数を作成"""
    
    def on_recognition_result(transcript, confidence, is_final):
        """音声認識結果処理"""
        try:
            if transcript.strip():
                # 結果表示
                status = "🎯 最終" if is_final else "📝 途中"
                print(f"\n{status}認識結果:")
                print(f"  発話者: {speaker_name}")
                print(f"  内容: {transcript}")
                print(f"  信頼度: {confidence:.2f}")
                
                if transcription_only:
                    print("  翻訳: スキップ（transcription-onlyモード）")
                else:
                    # TODO: 翻訳機能実装
                    print(f"  翻訳({target_lang}): [翻訳機能未実装]")
                print("-" * 50)
                
        except Exception as e:
            print(f"⚠️ 認識結果処理エラー: {e}")
    
    return on_recognition_result


def setup_signal_handlers(audio_capture, speech_recognition):
    """シグナルハンドラー設定"""
    def signal_handler(signum, frame):
        print(f"\n🛑 終了シグナル受信 (シグナル: {signum})")
        print("システム終了中...")
        
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