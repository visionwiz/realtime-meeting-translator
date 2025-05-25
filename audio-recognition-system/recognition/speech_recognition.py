import sys
import os
import datetime
import queue
import wave
import time
import numpy as np
import pyaudio
from language_config import LanguageConfig

if sys.platform == 'darwin':
    import mlx_whisper
    try:
        from lightning_whisper_mlx import LightningWhisperMLX
        LIGHTNING_WHISPER_AVAILABLE = True
    except ImportError:
        LIGHTNING_WHISPER_AVAILABLE = False
        print("Warning: lightning-whisper-mlx not available. Using standard mlx-whisper.")
else:
    import whisper

class SpeechRecognition:
    def __init__(self, config, processing_queue, translation_queue, args, lang_config):
        self.config = config
        self.processing_queue = processing_queue
        self.translation_queue = translation_queue
        self.args = args
        self.lang_config = lang_config

        # mlx-whisper最適化モデルの初期化
        if sys.platform == 'darwin':
            if getattr(args, 'use_lightning_whisper', False) and LIGHTNING_WHISPER_AVAILABLE:
                print("🚀 Lightning Whisper MLX使用（10倍高速化）")
                quantization = getattr(args, 'quantization', 'none')
                quant = quantization if quantization != 'none' else None
                # Lightning Whisper MLXでは多言語対応モデルを使用
                model_name = "large-v3" if "large" in args.model_size else args.model_size
                
                try:
                    # 量子化の互換性チェック
                    if quant is not None:
                        # まず量子化なしでモデルをロードしてから量子化を試行
                        print(f"量子化（{quantization}）を試行中...")
                        self.lightning_model = LightningWhisperMLX(
                            model=model_name,
                            batch_size=12,
                            quant=None  # 最初は量子化なし
                        )
                        # 量子化は後で適用する（ランタイムで）
                        self.quantization_mode = quantization
                        print(f"⚡ Lightning Whisper初期化完了 - モデル: {args.model_size}, 量子化: {quantization}（実行時適用）")
                    else:
                        self.lightning_model = LightningWhisperMLX(
                            model=model_name,
                            batch_size=12,
                            quant=None
                        )
                        self.quantization_mode = None
                        print(f"⚡ Lightning Whisper初期化完了 - モデル: {args.model_size}, 量子化: なし")
                    
                    self.use_lightning = True
                    
                except Exception as e:
                    print(f"⚠️ Lightning Whisper初期化エラー: {e}")
                    print("標準MLX Whisperにフォールバック")
                    self.use_lightning = False
                    self.quantization_mode = None
            else:
                print("⚡ MLX Whisper使用（3-4倍高速化）")
                self.use_lightning = False
                print(f"MLX Whisper初期化完了 - モデル: {args.model_size}")
        else:
            self.model = whisper.load_model(self.args.model_size)
            self.use_lightning = False

        os.makedirs(self.args.output_dir, exist_ok=True)
        current_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file_path = os.path.join(
            self.args.output_dir,
            f"recognized_audio_log_{self.lang_config.source_lang}_{current_time}.txt"
        )

    def recognition_thread(self, is_running):
        last_text = ""
        last_text_time = 0
        
        while is_running.is_set():
            try:
                audio_data = self.processing_queue.get(timeout=1)
                normalized_audio = self.normalize_audio(audio_data)
                
                if self.args.debug:
                    print("\n音声認識処理開始")
                    self.save_audio_debug(audio_data, f"debug_audio_{time.time()}.wav")
                
                try:
                    if sys.platform == 'darwin':
                        if self.use_lightning:
                            # Lightning Whisper MLX（10倍高速化）
                            import tempfile
                            import soundfile as sf
                            start_time = time.time()
                            try:
                                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_file:
                                    sf.write(temp_file.name, normalized_audio, self.config.RATE)
                                    result = self.lightning_model.transcribe(audio_path=temp_file.name)
                                import os
                                os.unlink(temp_file.name)
                                processing_time = time.time() - start_time
                                if self.args.debug:
                                    print(f"⚡ Lightning Whisper処理時間: {processing_time:.2f}秒")
                            except Exception as lightning_error:
                                print(f"⚠️ Lightning Whisper処理エラー: {lightning_error}")
                                # 標準mlx-whisperにフォールバック
                                start_time = time.time()
                                model_repo = getattr(self.args, 'model_path', None) or f"mlx-community/whisper-{self.args.model_size}-mlx"
                                result = mlx_whisper.transcribe(normalized_audio,
                                                                language=self.lang_config.source_lang,
                                                                path_or_hf_repo=model_repo,
                                                                verbose=False
                                )
                                processing_time = time.time() - start_time
                                if self.args.debug:
                                    print(f"⚡ フォールバックMLX Whisper処理時間: {processing_time:.2f}秒")
                        else:
                            # 標準mlx-whisper（3-4倍高速化）
                            start_time = time.time()
                            model_repo = getattr(self.args, 'model_path', None) or f"mlx-community/whisper-{self.args.model_size}-mlx"
                            result = mlx_whisper.transcribe(normalized_audio,
                                                            language=self.lang_config.source_lang,
                                                            path_or_hf_repo=model_repo,
                                                            verbose=False  # 高速化のため詳細出力を無効化
                            )
                            processing_time = time.time() - start_time
                            if self.args.debug:
                                print(f"⚡ MLX Whisper処理時間: {processing_time:.2f}秒")
                    else:
                        result = self.model.transcribe(normalized_audio,
                                                       language=self.lang_config.source_lang
                        )
                except Exception as e:
                    print(f"音声認識エラー: {e}")
                    continue
                
                # no_speech_probチェック（幻聴防止）
                no_speech_prob = 0.0
                if 'segments' in result and len(result['segments']) > 0:
                    no_speech_prob = result['segments'][0].get('no_speech_prob', 0.0)
                
                # 無音確率が高い場合は幻聴として破棄
                NO_SPEECH_THRESHOLD = 0.5  # 50%以上の無音確率で破棄
                if no_speech_prob > NO_SPEECH_THRESHOLD:
                    if self.args.debug:
                        print(f"🚫 幻聴検出: 無音確率 {no_speech_prob:.2f} > 閾値 {NO_SPEECH_THRESHOLD}")
                    continue
                
                text = result['text'].strip()
                
                current_time = time.time()
                if text and (text != last_text or current_time - last_text_time > 5):
                    self.print_with_strictly_controlled_linebreaks(text)
                    last_text = text
                    last_text_time = current_time
                    if self.translation_queue:
                        self.translation_queue.put(text)
                    # 認識結果をファイルに追記
                    with open(self.log_file_path, "a", encoding="utf-8") as log_file:
                        log_file.write(text + "\n")

                elif self.args.debug:
                    print("処理後のテキストが空か、直前の文と同じため出力をスキップします")

            except queue.Empty:
                if self.args.debug:
                    print("認識キューが空です")
            except Exception as e:
                print(f"\nエラー (認識スレッド): {e}", flush=True)

    def normalize_audio(self, audio_data):
        if self.config.FORMAT == pyaudio.paFloat32:
            return np.clip(audio_data, -1.0, 1.0)
        elif self.config.FORMAT == pyaudio.paInt8:
            return audio_data.astype(np.float32) / 128.0
        elif self.config.FORMAT == pyaudio.paInt16:
            return audio_data.astype(np.float32) / 32768.0
        elif self.config.FORMAT == pyaudio.paInt32:
            return audio_data.astype(np.float32) / 2147483648.0
        else:
            raise ValueError(f"Unsupported audio format: {self.config.FORMAT}")

    def save_audio_debug(self, audio_data, filename):
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(self.config.CHANNELS)
            wf.setsampwidth(pyaudio.get_sample_size(self.config.FORMAT))
            wf.setframerate(self.config.RATE)
            wf.writeframes(audio_data.tobytes())

    @staticmethod
    def is_sentence_end(word):
        # 日本語と英語の文末記号
        sentence_end_chars = ('.', '!', '?', '。', '！', '？')
        return word.endswith(sentence_end_chars)

    def print_with_strictly_controlled_linebreaks(self, text):
        words = text.split()
        buffer = []
        final_output = ""
        for i, word in enumerate(words):
            buffer.append(word)
            
            if SpeechRecognition.is_sentence_end(word) or i == len(words) - 1:
                line = ' '.join(buffer)
                final_output += line
                if SpeechRecognition.is_sentence_end(word):
                    final_output += '\n'
                elif i == len(words) - 1:
                    final_output += ' '
                buffer = []

        if buffer:
            line = ' '.join(buffer)
            final_output += line

        # コンソールに出力
        print(final_output, end='', flush=True)

