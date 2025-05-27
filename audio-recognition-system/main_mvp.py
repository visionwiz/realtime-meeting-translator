"""
MVP版メインスクリプト
音声認識 → Claude翻訳 → Google Docs出力の統合システム

MVP戦略: シンプルで確実な動作を優先、複雑な最適化は後回し
"""

import sys
import argparse
import threading
import time
import queue
import logging
import os
import numpy as np
from datetime import datetime
from typing import Optional

# 既存モジュール
from config import AudioConfig
from audio.capture import AudioCapture
from audio.processing import AudioProcessing
from recognition.speech_recognition import SpeechRecognition
from utils.resource_manager import ResourceManager
from language_config import LanguageConfig

# MVP新規モジュール
sys.path.append(os.path.join(os.path.dirname(__file__), 'config'))
sys.path.append(os.path.join(os.path.dirname(__file__), 'translation'))  
sys.path.append(os.path.join(os.path.dirname(__file__), 'output'))
from mvp_config import MVPConfig, create_mvp_config_from_args
from claude_translator import ClaudeTranslator, TranslationResult
from basic_google_docs_writer import BasicGoogleDocsWriter, MeetingEntry

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class MVPAudioRecognitionSystem:
    """MVP版音声認識・翻訳・Google Docs出力システム"""
    
    def __init__(self, mvp_config: MVPConfig):
        """
        システム初期化
        
        Args:
            mvp_config: MVP設定
        """
        self.mvp_config = mvp_config
        self.is_running = threading.Event()
        self.is_running.set()
        
        # レガシー設定との互換性のため一時的にargs風オブジェクトを作成
        class Args:
            def __init__(self, mvp_config):
                self.input_device = mvp_config.input_device
                self.source_lang = mvp_config.source_lang
                self.target_lang = mvp_config.target_lang
                self.output_dir = mvp_config.output_dir or "logs"
                # 既存システムで必要な値を設定
                self.volume_threshold = 0.01
                self.max_silence_duration = 3.0
                self.min_audio_duration = 1.0
                self.max_audio_duration = 30.0
                # AudioConfig用の追加属性
                self.format = "int16"
                self.channels = 1
                self.rate = mvp_config.sample_rate
                self.chunk = 1024
                self.buffer_duration = 5.0
                # SpeechRecognition用の追加属性
                self.model_size = mvp_config.speech_model
                self.compute_type = "float16"
                self.beam_size = 5
                self.best_of = 5
                self.temperature = 0.0
                self.debug = True
                self.save_raw_audio = False
                self.save_processed_audio = False
        
        self.args = Args(mvp_config)
        
        # 既存システム互換のためのAudioConfig作成
        self.config = AudioConfig(self.args)
        
        # 言語設定
        self.lang_config = LanguageConfig(
            source_lang=mvp_config.source_lang,
            target_lang=mvp_config.target_lang
        )
        
        # キューシステム（既存システム互換）
        self.audio_queue = queue.Queue()
        self.processing_queue = queue.Queue()
        self.recognition_queue = queue.Queue()  # 音声認識結果用
        
        # リソース管理
        self.resource_manager = ResourceManager()
        
        # 音声認識システム（既存）
        self.audio_capture = AudioCapture(self.config, self.audio_queue, self.args)
        self.audio_processing = AudioProcessing(self.config, self.audio_queue, self.processing_queue)
        self.speech_recognition = SpeechRecognition(
            self.config, self.processing_queue, self.recognition_queue, self.args, self.lang_config
        )
        
        # Google Cloud Speech V2ストリーミング用の音声データ中継設定
        self.streaming_bridge_active = True
        
        # 音声認識専用モード用のログファイル設定
        if mvp_config.transcription_only:
            import datetime
            current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = mvp_config.output_dir or "logs"
            os.makedirs(output_dir, exist_ok=True)
            self.transcription_log_path = os.path.join(
                output_dir,
                f"transcription_only_{mvp_config.source_lang}_{current_time}.txt"
            )
        
        # 翻訳システム（新規）
        self.translator = None
        if not mvp_config.disable_translation:
            self.translator = ClaudeTranslator(mvp_config.claude_api_key, mvp_config.claude_model_name)
            logger.info("翻訳機能を有効化")
        else:
            logger.info("翻訳機能を無効化")
        
        # Google Docs出力（新規）
        self.docs_writer = None
        if not mvp_config.disable_docs_output and mvp_config.google_docs_id:
            try:
                self.docs_writer = BasicGoogleDocsWriter(
                    mvp_config.google_credentials_path,
                    mvp_config.google_token_path
                )
                self.docs_writer.set_document_id(mvp_config.google_docs_id)
                logger.info("Google Docs出力を有効化")
            except Exception as e:
                logger.error(f"Google Docs初期化エラー: {e}")
                self.docs_writer = None
        else:
            if mvp_config.disable_docs_output:
                logger.info("Google Docs出力を無効化")
            else:
                logger.info("Google Docs出力を無効化（ドキュメントID未指定）")
        
        logger.info("MVP音声認識システム初期化完了")
    
    def streaming_bridge_thread(self):
        """処理された音声データをGoogle Cloud Speech V2ストリーミングに送信するブリッジスレッド"""
        logger.info("音声ストリーミングブリッジスレッド開始")
        
        while self.streaming_bridge_active and self.is_running.is_set():
            try:
                # 処理済み音声データを取得
                audio_data = self.processing_queue.get(timeout=1.0)
                
                if audio_data is not None:
                    # 音声データをバイト形式に変換してストリーミングAPIに送信
                    if isinstance(audio_data, np.ndarray):
                        # float32をint16に変換
                        if audio_data.dtype == np.float32:
                            audio_int16 = (audio_data * 32767).astype(np.int16)
                        else:
                            audio_int16 = audio_data.astype(np.int16)
                        
                        # バイトデータに変換
                        audio_bytes = audio_int16.tobytes()
                        
                        # Google Cloud Speech V2の制限（25,600バイト）に合わせてチャンクを分割
                        max_chunk_size = 25600
                        chunk_count = 0
                        for i in range(0, len(audio_bytes), max_chunk_size):
                            chunk = audio_bytes[i:i + max_chunk_size]
                            # Google Cloud Speech V2ストリーミングに送信
                            self.speech_recognition.add_audio_data(chunk)
                            chunk_count += 1
                            
                            if self.args.debug:
                                print(f"🔗 チャンク{chunk_count}送信: {len(chunk)}バイト (元サイズ: {len(audio_bytes)})")
                        
                        if self.args.debug and chunk_count > 1:
                            print(f"✅ 分割完了: {chunk_count}チャンクに分割")
                
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"ストリーミングブリッジエラー: {e}")
                time.sleep(0.1)
        
        logger.info("音声ストリーミングブリッジスレッド終了")
    
    def translation_and_output_thread(self):
        """翻訳とGoogle Docs出力を処理するスレッド"""
        logger.info("翻訳・出力スレッド開始")
        
        # セッションヘッダーを書き込み
        if self.docs_writer:
            session_info = {
                'speaker_name': self.mvp_config.speaker_name,
                'source_lang': self.mvp_config.source_lang,
                'target_lang': self.mvp_config.target_lang
            }
            self.docs_writer.write_session_header(session_info)
        
        while self.is_running.is_set():
            try:
                # 音声認識結果を取得（タイムアウト付き）
                if not self.recognition_queue.empty():
                    recognition_result = self.recognition_queue.get(timeout=1.0)
                    
                    # 空文字や無効な結果をスキップ
                    if not recognition_result or not recognition_result.strip():
                        continue
                    
                    logger.info(f"音声認識結果: {recognition_result}")
                    
                    # 翻訳機能が無効な場合は認識結果のみ出力
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
                        logger.info(f"翻訳成功: {translation_result.translated_text}")
                        
                        # Google Docs出力（出力機能が有効な場合のみ）
                        if self.docs_writer and not self.mvp_config.disable_docs_output:
                            meeting_entry = MeetingEntry(
                                timestamp=datetime.now(),
                                speaker_name=self.mvp_config.speaker_name,
                                original_text=translation_result.original_text,
                                translated_text=translation_result.translated_text,
                                source_lang=self.mvp_config.source_lang,
                                target_lang=self.mvp_config.target_lang
                            )
                            
                            if self.docs_writer.write_meeting_entry(meeting_entry):
                                logger.info("Google Docsに出力完了")
                            else:
                                logger.error("Google Docs出力失敗")
                        
                        # コンソール出力（フォールバック）
                        self._print_result(translation_result)
                    
                    else:
                        logger.error(f"翻訳失敗: {translation_result.error_message}")
                        # 翻訳失敗時は原文のみ出力（出力機能が有効な場合のみ）
                        if self.docs_writer and not self.mvp_config.disable_docs_output:
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
                logger.error(f"翻訳・出力スレッドでエラー: {e}")
                time.sleep(1.0)
        
        logger.info("翻訳・出力スレッド終了")
    
    def transcription_only_thread(self):
        """音声認識専用スレッド（翻訳・出力なし）"""
        logger.info("音声認識専用スレッド開始")
        
        while self.is_running.is_set():
            try:
                # 音声認識結果を取得（タイムアウト付き）
                if not self.recognition_queue.empty():
                    recognition_result = self.recognition_queue.get(timeout=1.0)
                    
                    # 空文字や無効な結果をスキップ
                    if not recognition_result or not recognition_result.strip():
                        continue
                    
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    # コンソール出力
                    print(f"\n[{timestamp}] {self.mvp_config.speaker_name}:")
                    print(f"認識結果({self.mvp_config.source_lang}): {recognition_result}")
                    print("-" * 50)
                    
                    # ファイル出力
                    with open(self.transcription_log_path, "a", encoding="utf-8") as log_file:
                        log_file.write(f"[{timestamp}] {recognition_result}\n")
                    
                    logger.info(f"音声認識結果: {recognition_result}")
                
                else:
                    time.sleep(0.1)  # CPU使用率軽減
                    
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"音声認識専用スレッドでエラー: {e}")
                time.sleep(1.0)
        
        logger.info("音声認識専用スレッド終了")
    
    def _print_result(self, translation_result: TranslationResult):
        """結果をコンソールに出力"""
        timestamp = datetime.fromtimestamp(translation_result.timestamp).strftime("%H:%M:%S")
        print(f"\n[{timestamp}] {self.mvp_config.speaker_name}:")
        print(f"原文({translation_result.source_lang}): {translation_result.original_text}")
        print(f"翻訳({translation_result.target_lang}): {translation_result.translated_text}")
        print("-" * 50)
    
    def run(self):
        """システム実行"""
        logger.info("MVP音声認識システム開始")
        
        # 設定表示
        self.mvp_config.print_config()
        
        # API接続テスト
        if not self._test_connections():
            logger.error("API接続テストに失敗しました")
            return
        
        # スレッド作成（機能無効化フラグに応じて分岐）
        threads = [
            threading.Thread(target=self.audio_capture.capture_thread, args=(self.is_running,)),
            threading.Thread(target=self.audio_processing.processing_thread, args=(self.is_running,)),
            threading.Thread(target=self.streaming_bridge_thread),
            threading.Thread(target=self.speech_recognition.run_recognition_thread),
        ]
        
        # 翻訳・出力スレッドまたは音声認識専用スレッドを追加
        if self.mvp_config.transcription_only:
            threads.append(threading.Thread(target=self.transcription_only_thread))
        else:
            threads.append(threading.Thread(target=self.translation_and_output_thread))
        
        # スレッド開始
        for thread in threads:
            thread.start()
            logger.info(f"スレッド開始: {thread.name}")
        
        if self.mvp_config.transcription_only:
            print("\n=== MVP音声認識専用システム稼働中 ===")
            print(f"発話者: {self.mvp_config.speaker_name}")
            print(f"認識言語: {self.mvp_config.source_lang}")
            print(f"出力ファイル: {self.transcription_log_path}")
        else:
            print("\n=== MVP音声認識・翻訳・Google Docs出力システム稼働中 ===")
            print(f"発話者: {self.mvp_config.speaker_name}")
            if not self.mvp_config.disable_translation:
                print(f"翻訳方向: {self.mvp_config.source_lang} → {self.mvp_config.target_lang}")
            else:
                print(f"認識言語: {self.mvp_config.source_lang} (翻訳無効)")
            if self.mvp_config.disable_docs_output:
                print("Google Docs出力: 無効")
        print("Ctrl+Cで終了")
        print("=" * 60)
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n終了処理中...")
            logger.info("終了シグナル受信")
            self.is_running.clear()
            self.streaming_bridge_active = False
            self.speech_recognition.stop_recognition()
        
        # スレッド終了待ち
        for thread in threads:
            thread.join(timeout=5.0)
            logger.info(f"スレッド終了: {thread.name}")
        
        print("MVP システムを終了しました。")
        logger.info("MVP音声認識システム終了")
    
    def _test_connections(self) -> bool:
        """API接続テスト"""
        logger.info("API接続テスト開始")
        
        # Claude翻訳テスト（翻訳機能が有効な場合のみ）
        if hasattr(self, 'translator') and self.translator:
            if not self.translator.test_connection():
                logger.error("Claude API接続テスト失敗")
                return False
            logger.info("✅ Claude API接続成功")
        else:
            logger.info("🚫 Claude翻訳テストをスキップ（翻訳機能無効）")
        
        # Google Docs接続テスト（出力機能が有効な場合のみ）
        if hasattr(self, 'docs_writer') and self.docs_writer:
            if not self.docs_writer.test_connection():
                logger.error("Google Docs API接続テスト失敗")
                return False
            logger.info("✅ Google Docs API接続成功")
            
            # テスト結果を踏まえたドキュメントアクセス確認
            if not self.docs_writer.verify_document_access():
                logger.error("Google Docsドキュメントアクセス確認失敗")
                return False
            logger.info("✅ Google Docsドキュメントアクセス確認成功")
        else:
            logger.info("🚫 Google Docs出力テストをスキップ（出力機能無効）")
        
        logger.info("API接続テスト完了")
        return True


def create_argument_parser() -> argparse.ArgumentParser:
    """コマンドライン引数パーサーを作成"""
    parser = argparse.ArgumentParser(
        description="MVP版 リアルタイム音声認識・翻訳・Google Docs出力システム"
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
        '--model', 
        choices=['tiny', 'base', 'small', 'medium', 'large-v2', 'large-v3'],
        default='large-v3',
        help='音声認識モデル (デフォルト: large-v3)'
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
    
    return parser


def main():
    """メイン関数"""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    try:
        # MVP設定作成
        mvp_config = create_mvp_config_from_args(args)
        
        # 設定検証
        is_valid, errors = mvp_config.validate()
        if not is_valid:
            logger.error("設定エラー:")
            for error in errors:
                logger.error(f"  - {error}")
            sys.exit(1)
        
        # システム実行
        system = MVPAudioRecognitionSystem(mvp_config)
        system.run()
        
    except KeyboardInterrupt:
        logger.info("ユーザーによる中断")
    except Exception as e:
        logger.error(f"システムエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 