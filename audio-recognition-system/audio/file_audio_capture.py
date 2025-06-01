import time
import threading
import wave
import numpy as np
from pathlib import Path
import librosa
import soundfile as sf

class FileAudioCapture:
    """録音ファイルをストリーミング認識に流し込むクラス"""
    
    def __init__(self, callback_func, audio_file_path, sample_rate=16000, chunk_size=1600, 
                 realtime_speed=1.0, verbose=False, completion_callback=None):
        """
        Args:
            callback_func: 音声データを送信するコールバック関数
            audio_file_path: 音声ファイルのパス
            sample_rate: 出力サンプリングレート（16kHz推奨）
            chunk_size: チャンクサイズ（1600 = 100ms @ 16kHz）
            realtime_speed: 再生速度倍率（1.0=リアルタイム、2.0=2倍速、0.5=0.5倍速）
            verbose: 詳細ログ表示
            completion_callback: 音声ファイル完了時のコールバック関数
        """
        self.callback_func = callback_func
        self.audio_file_path = Path(audio_file_path)
        self.target_sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.realtime_speed = realtime_speed
        self.verbose = verbose
        self.completion_callback = completion_callback  # 完了通知用
        self.is_running = False
        
        # 音声ファイル読み込み・前処理
        self.audio_data = self._load_and_preprocess_audio()
        self.total_chunks = len(self.audio_data) // chunk_size
        self.duration_seconds = len(self.audio_data) / sample_rate
        
        print(f"🎵 音声ファイル読み込み完了")
        print(f"   ファイル: {self.audio_file_path.name}")
        print(f"   長さ: {self.duration_seconds:.1f}秒")
        print(f"   サンプル数: {len(self.audio_data):,}")
        print(f"   チャンク数: {self.total_chunks}")
        print(f"   再生速度: {realtime_speed}x")
        if realtime_speed != 1.0:
            actual_duration = self.duration_seconds / realtime_speed
            print(f"   実際の再生時間: {actual_duration:.1f}秒")
    
    def _load_and_preprocess_audio(self):
        """音声ファイル読み込み・前処理"""
        try:
            # librosaで音声ファイル読み込み（様々なフォーマット対応）
            audio_data, original_sr = librosa.load(
                str(self.audio_file_path), 
                sr=self.target_sample_rate,  # 自動リサンプリング
                mono=True  # モノラル変換
            )
            
            if self.verbose:
                print(f"🔧 音声ファイル詳細:")
                print(f"   元サンプリングレート: {original_sr}Hz")
                print(f"   変換後サンプリングレート: {self.target_sample_rate}Hz")
                print(f"   音声データ型: {audio_data.dtype}")
                print(f"   音声データ範囲: {audio_data.min():.3f} ~ {audio_data.max():.3f}")
            
            # int16形式に変換（Google Cloud Speech API要件）
            if audio_data.dtype != np.int16:
                # float32 (-1.0~1.0) から int16 (-32768~32767) に変換
                audio_data = (audio_data * 32767).astype(np.int16)
                
            return audio_data
            
        except Exception as e:
            print(f"❌ 音声ファイル読み込みエラー: {e}")
            print(f"   対応形式: WAV, MP3, FLAC, M4A, OGG等")
            raise
    
    def start_capture(self):
        """音声ファイル再生開始（ストリーミング送信）"""
        self.is_running = True
        
        print(f"🎬 音声ファイル再生開始")
        if self.realtime_speed != 1.0:
            print(f"   再生速度: {self.realtime_speed}x（テスト高速化）")
        
        # チャンク間隔計算（リアルタイム再生用）
        chunk_duration = self.chunk_size / self.target_sample_rate  # 秒
        actual_interval = chunk_duration / self.realtime_speed  # 再生速度考慮
        
        if self.verbose:
            print(f"🔧 ストリーミング設定:")
            print(f"   チャンク長: {chunk_duration*1000:.1f}ms")
            print(f"   送信間隔: {actual_interval*1000:.1f}ms")
        
        current_chunk = 0
        start_time = time.time()
        
        try:
            while self.is_running and current_chunk < self.total_chunks:
                # チャンクデータ取得
                start_idx = current_chunk * self.chunk_size
                end_idx = min(start_idx + self.chunk_size, len(self.audio_data))
                chunk_data = self.audio_data[start_idx:end_idx]
                
                # int16形式のPCMデータをbytes形式に変換
                pcm_bytes = chunk_data.tobytes()
                
                # コールバック関数に送信（SimpleAudioCaptureと同じ形式）
                self.callback_func(pcm_bytes)
                
                # 進捗表示
                if current_chunk % 50 == 0 or self.verbose:  # 5秒おき（50チャンク x 100ms）
                    elapsed_audio_time = current_chunk * chunk_duration
                    progress = (current_chunk / self.total_chunks) * 100
                    print(f"🎵 再生中: {elapsed_audio_time:.1f}s / {self.duration_seconds:.1f}s ({progress:.1f}%)")
                
                current_chunk += 1
                
                # タイミング調整（リアルタイム再生）
                expected_time = start_time + (current_chunk * actual_interval)
                current_time = time.time()
                sleep_time = expected_time - current_time
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                elif self.verbose and sleep_time < -0.1:  # 100ms以上の遅延
                    print(f"⚠️ 処理遅延: {-sleep_time*1000:.1f}ms")
            
            print(f"✅ 音声ファイル再生完了 ({current_chunk}/{self.total_chunks} チャンク)")
            
            # 音声認識ストリームに終了シグナルを送信（空データ送信で終了を通知）
            try:
                # 少し待機してから終了処理を実行
                time.sleep(0.5)
                # 音声認識システムに終了を通知するため、空データを送信
                self.callback_func(b'')  # 空のバイトデータで終了を知らせる
            except Exception as e:
                if self.verbose:
                    print(f"⚠️ 終了シグナル送信エラー: {e}")
            
            if self.completion_callback:
                self.completion_callback()
            
        except Exception as e:
            print(f"❌ 音声ファイル再生エラー: {e}")
        finally:
            self.is_running = False
    
    def stop_capture(self):
        """音声ファイル再生停止"""
        self.is_running = False
        print("🛑 音声ファイル再生停止")
    
    def pause_capture(self):
        """一時停止（互換性のため）"""
        print("⏸️ ファイル再生一時停止（未実装）")
    
    def resume_capture(self):
        """再開（互換性のため）"""
        print("▶️ ファイル再生再開（未実装）")


def get_supported_formats():
    """サポート音声形式一覧"""
    return [
        "WAV (推奨) - .wav",
        "FLAC (高品質) - .flac", 
        "MP3 - .mp3",
        "M4A/AAC - .m4a, .aac",
        "OGG - .ogg",
        "その他 librosa対応形式"
    ]


def validate_audio_file(file_path):
    """音声ファイル検証"""
    file_path = Path(file_path)
    
    if not file_path.exists():
        return False, f"ファイルが見つかりません: {file_path}"
    
    try:
        # ファイル読み込みテスト
        audio_data, sr = librosa.load(str(file_path), sr=None, duration=1.0)  # 最初の1秒のみ
        duration = librosa.get_duration(path=str(file_path))
        
        return True, {
            "duration": duration,
            "sample_rate": sr,
            "channels": "mono" if len(audio_data.shape) == 1 else f"{audio_data.shape[1]}ch"
        }
    except Exception as e:
        return False, f"音声ファイル読み込みエラー: {e}"


if __name__ == "__main__":
    # テスト用
    print("📁 サポート音声形式:")
    for fmt in get_supported_formats():
        print(f"  - {fmt}")
    
    # ファイル検証例
    test_file = "test_audio.wav"
    is_valid, result = validate_audio_file(test_file)
    if is_valid:
        print(f"✅ {test_file}: {result}")
    else:
        print(f"❌ {test_file}: {result}") 