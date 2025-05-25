# オンライン会議用リアルタイム音声認識・翻訳・Google Docs出力システム実装プロンプト

## システム概要
既存のaudio-recognition-systemを基盤として、オンライン会議での個人発話を対象とした音声認識・翻訳・Google Docs自動出力システムを実装してください。

## 技術選択の根拠
**言語: Python継続**
- **既存システム活用**: 音声認識・翻訳コードの再利用により開発期間50%短縮
- **統合開発環境**: 単一言語による管理の簡素化
- **技術リスク最小化**: 新技術導入リスクの回避
- **Google API対応**: `google-api-python-client`による公式サポート（継続更新中）
- **パフォーマンス**: JavaScript/Node.jsとの処理速度差は体感レベルで差異なし

## 背景・要件
- 社内のオンライン会議に日本語話者と英語話者が複数人参加
- 各発話者が自分のデバイス（Mac）で個別にシステムを実行
- 通訳がいないため、リアルタイムでの文字起こし・翻訳が必要

## システムのゴール
1. 各発話者が指定した言語で発話した内容を文字起こし
2. 文字起こし結果を指定した対象言語に翻訳
3. 発話者毎に文字起こしテキストと翻訳テキストをGoogleドキュメントにリアルタイム出力
4. 発話から翻訳出力まで10秒程度の遅延は許容
   - macOS特化モデル使用時は遅延を大幅短縮（目標3-5秒）
   - **チャンクサイズによる遅延調整**: 10-15秒チャンクで精度優先、6-8秒で低遅延
   - **適応的調整**: VAD連携により発話パターンに応じた最適化
   
## 技術仕様

### 音声入力
- **入力デバイス**: ヘッドセットマイク推奨（例: OpenComm by Shokz）、内蔵マイクも対応
- **デバイス指定**: コマンドライン引数で入力デバイスインデックスを指定
- **対象音声**: 利用者自身の発話のみ（他の参加者の音声は除外）
- **音声形式**: 16kHz, モノラル

### 音声認識
- **推奨**: macOS特化モデル優先、標準Whisperでフォールバック
  - **macOS**: WhisperKit（15倍高速化、19%レイテンシ改善、45%メモリ削減）
  - **フォールバック**: OpenAI Whisper large-v3（クロスプラットフォーム対応）
- **技術選択根拠**: 精度維持（WER 1.99%同等）しつつパフォーマンス大幅向上
- **プライバシー**: macOS特化モデルは完全ローカル処理
- **言語指定**: コマンドライン引数で発話言語を指定（自動判定不要）
- **チャンクサイズ最適化**: 精度とリアルタイム性のバランス
  - **推奨設定**: 10-15秒チャンク（会議での自然な発話区切りに対応）
  - **バッファサイズ**: 20-30秒（文脈保持と処理効率の最適化）
  - **オーバーラップ**: 2-3秒（文章途中分割の防止）
  - **適応的調整**: VAD連携による動的チャンクサイズ調整

### 翻訳
- **現在**: ローカルLLM（mlx-lm）
- **要求**: 高性能翻訳API（Claude 3.7 Sonnet推奨、OpenAI GPT-4oも対応）
- **翻訳方向**: 発話言語→対象言語（コマンドライン引数で指定）
- **API選択**: 環境変数で翻訳プロバイダーを指定可能
- **リアルタイム翻訳チャンク最適化**: 音声認識チャンクとの連携設計
  - **基本戦略**: 音声認識結果2-3チャンク分を統合して翻訳処理
  - **推奨設定**: 6-8セグメント/チャンク（約24-36秒の文脈）
  - **オーバーラップ**: 2セグメント（文脈継続性確保）
  - **適応的調整**: 発話パターンに応じた自動モード切り替え
  - **遅延制御**: 最大5-7秒以内（音声認識遅延と合わせて総計10秒以内）

### Google Docs出力
- **新機能**: Google Docs APIを使用したリアルタイム文書更新
- **技術選択**: `google-api-python-client`（Google公式ライブラリ）
- **認証方式**: OAuth 2.0（ユーザー認証）またはサービスアカウント（自動化）
- **出力形式**: 発話者別セクション、タイムスタンプ付き
- **内容**: 原文と翻訳文の両方を出力
- **ローカルファイル**: バイリンガルファイル出力を明示的に停止（Google Docsで統合管理するため）

## 実装要件

### 1. 既存システムの拡張
```
基盤: audio-recognition-system
├─ 音声キャプチャ: 既存のaudio/capture.py
├─ 音声処理: 既存のaudio/processing.py  
├─ 音声認識: recognition/optimized_speech_recognition.py（macOS特化+フォールバック）
├─ 翻訳: translation/translator.py（Claude API化）
└─ Google Docs出力: output/google_docs_writer.py（新規作成）
```

### 2. 新規実装が必要な機能

#### A. 高性能音声認識モジュール
- ファイル: `recognition/optimized_speech_recognition.py`
- 機能: macOS特化モデル優先、標準Whisperフォールバック
- 特徴: 15倍高速化、19%レイテンシ改善、45%メモリ削減
- 量子化: INT4/INT8による追加最適化
- 完全ローカル処理: プライバシー強化
- **チャンクサイズ最適化**: 精度とリアルタイム性の動的調整
  - 設定可能チャンクサイズ: 6-20秒（デフォルト12秒）
  - 適応的バッファリング: VAD連携による自動調整
  - オーバーラップ処理: 文脈保持による精度向上
  - パフォーマンスプロファイル: 高精度/バランス/低遅延モード

#### B. 高性能翻訳APIモジュール
- ファイル: `translation/api_translator.py`
- 機能: 複数の翻訳APIに対応（Claude 3.7 Sonnet、OpenAI GPT-4o等）
- API設定: `.env`ファイルからAPIキーとプロバイダー情報を取得
- プロバイダー切り替え: 環境変数による動的な翻訳サービス選択
- **重要**: 既存のバイリンガルファイル出力処理をコメントアウトすること
- **文脈バッファリング**: リアルタイム翻訳のための文脈管理
  - 翻訳履歴保持: 過去3-5回の翻訳結果を文脈として活用
  - 話者別文脈: 個人の発話パターンや専門用語の一貫性確保
  - 適応的文脈サイズ: API制限とレイテンシに応じた文脈量調整
  - メモリ効率化: 重要度による文脈の優先順位付けと圧縮

#### C. Google Docs出力モジュール  
- ファイル: `output/google_docs_writer.py`
- 機能: リアルタイムでの文書更新、発話者別セクション管理
- 認証: OAuth 2.0またはサービスアカウント

#### D. 設定管理の拡張
- ファイル: `config/api_config.py`
- 機能: 音声認識モデル選択、翻訳API、Google Docs APIの設定管理
- 環境変数読み込み: `python-dotenv`を使用した`.env`ファイルの読み込み
- プロバイダー管理: 音声認識・翻訳APIプロバイダーの動的切り替え機能
- パフォーマンス設定: 量子化レベル、最適化モードの管理
- **チャンクサイズ設定管理**: 柔軟なパラメータ調整機能
  - 動的設定変更: 実行時でのチャンクサイズ調整
  - プロファイル管理: 精度優先/バランス/速度優先の設定プリセット
  - バリデーション: パラメータ範囲チェックとエラーハンドリング
  - 設定保存: ユーザー設定の永続化とプロファイル切り替え

### 3. コマンドライン引数の拡張
```bash
# ヘッドセットマイク使用例（macOS最適化モデル使用）
python main_with_translation_and_docs.py \
  --input-device 0 \
  --source-lang ja \
  --target-lang en \
  --speaker-name "田中太郎" \
  --google-docs-id "YOUR_DOCUMENT_ID" \
  --output-dir logs/meeting_20250101_1400 \
  --speech-model optimized \
  --quantization int4 \
  --chunk-size 12 \
  --buffer-size 25

# 内蔵マイク使用例（標準Whisperでフォールバック）
python main_with_translation_and_docs.py \
  --input-device 1 \
  --source-lang en \
  --target-lang ja \
  --speaker-name "John Smith" \
  --google-docs-id "YOUR_DOCUMENT_ID" \
  --speech-model whisper-large-v3 \
  --chunk-size 10 \
  --adaptive-chunk

# 高精度優先（長めのチャンク設定）
python main_with_translation_and_docs.py \
  --input-device 0 \
  --source-lang ja \
  --target-lang en \
  --speaker-name "田中太郎" \
  --google-docs-id "YOUR_DOCUMENT_ID" \
  --speech-model whisperkit \
  --chunk-size 15 \
  --buffer-size 30 \
  --overlap-size 3

# 低遅延優先（短めのチャンク設定）
python main_with_translation_and_docs.py \
  --input-device 0 \
  --source-lang en \
  --target-lang ja \
  --speaker-name "John Smith" \
  --google-docs-id "YOUR_DOCUMENT_ID" \
  --speech-model optimized \
  --chunk-size 8 \
  --buffer-size 16 \
  --performance-mode low-latency
```

### 4. 必要な新しい依存関係
```
# 翻訳API（プロバイダーに応じて選択）
anthropic>=0.25.0          # Claude API用
openai>=1.0.0              # OpenAI API用

# Google Docs API（公式ライブラリ・継続更新中）
google-api-python-client>=2.170.0  # 最新版（2025年5月更新）
google-auth-httplib2>=0.2.0
google-auth-oauthlib>=1.0.0
google-auth>=2.0.0

# 音声認識の高性能化（段階的導入）
# macOS特化モデル（優先）
whisperkit>=0.9.0          # macOS専用・15倍高速化
lightning-whisper-mlx>=1.0.0  # 代替選択肢・10倍高速化

# フォールバック（クロスプラットフォーム対応）
whisper>=1.1.10            # OpenAI Whisper large-v3対応

# 設定管理
python-dotenv>=1.0.0
pydantic>=2.0.0             # 設定バリデーションと型安全性
pydantic-settings>=2.0.0    # 環境変数設定管理
```

### 5. 環境変数設定（.envファイル）
```bash
# .env ファイルの例
TRANSLATION_API_KEY=your_translation_api_key_here
TRANSLATION_API_PROVIDER=claude  # claude, openai, etc.
GOOGLE_DOCS_CREDENTIALS_PATH=path/to/credentials.json
GOOGLE_DOCS_TOKEN_PATH=path/to/token.json

# 音声認識最適化設定
SPEECH_MODEL_PREFER_OPTIMIZED=true    # macOS特化モデル優先使用
SPEECH_MODEL_QUANTIZATION=int4        # 量子化レベル（int4, int8, none）
SPEECH_MODEL_FALLBACK=whisper-large-v3 # フォールバック時のモデル

# チャンクサイズ・バッファリング設定（精度とリアルタイム性の調整）
AUDIO_CHUNK_SIZE=12                   # 音声チャンクサイズ（秒）：10-15秒推奨
AUDIO_BUFFER_SIZE=25                  # 音声バッファサイズ（秒）：20-30秒推奨
AUDIO_OVERLAP_SIZE=2.5                # オーバーラップサイズ（秒）：2-3秒推奨
AUDIO_VAD_ENABLED=true                # VAD（音声活動検出）有効化
AUDIO_ADAPTIVE_CHUNK=true             # 適応的チャンクサイズ調整
AUDIO_MIN_CHUNK_SIZE=6                # 最小チャンクサイズ（秒）
AUDIO_MAX_CHUNK_SIZE=20               # 最大チャンクサイズ（秒）
AUDIO_SILENCE_THRESHOLD=1.5           # 無音検出閾値（秒）

# 翻訳チャンクサイズ設定（リアルタイム会議最適化）
TRANSLATION_CHUNK_SEGMENTS=6          # 翻訳チャンクセグメント数：4-10推奨
TRANSLATION_OVERLAP_SEGMENTS=2        # 翻訳オーバーラップセグメント数：1-3推奨
TRANSLATION_MAX_DELAY=5.0             # 最大翻訳遅延（秒）：2-10秒
TRANSLATION_STRATEGY=contextual       # 翻訳戦略：immediate/contextual/contextual_extended
TRANSLATION_ADAPTIVE_MODE=true        # 適応的翻訳モード切り替え
TRANSLATION_API_RATE_LIMIT=15         # API呼び出し制限（回/分）

# LLM文脈バッファリング設定（翻訳品質とメモリ効率の調整）
LLM_CONTEXT_HISTORY_COUNT=5           # 翻訳履歴保持数：3-10推奨
LLM_MAX_CONTEXT_TOKENS=8000           # 最大文脈トークン数：4000-15000
LLM_CONTEXT_COMPRESSION_THRESHOLD=0.8 # 文脈圧縮開始閾値：0.6-0.9
LLM_SPEAKER_CONTEXT_DURATION=300      # 話者別文脈保持時間（秒）：180-600
LLM_CONTEXT_UPDATE_FREQUENCY=adaptive # 文脈更新頻度：immediate/adaptive/batch
LLM_CONTEXT_PRIORITY_MODE=balanced    # 文脈優先度：speed/balanced/quality
LLM_CONTEXT_MEMORY_LIMIT=50          # 文脈メモリ制限（MB）：20-100
```

## チャンクサイズ最適化の詳細仕様

### 1. パフォーマンスプロファイル設定
```json
# config/performance_profiles.json
{
  "profiles": {
    "high_precision": {
      "name": "高精度優先",
      "description": "最高品質の文字起こしを優先（遅延は許容）",
      "chunk_size": 15,
      "buffer_size": 30,
      "overlap_size": 3,
      "vad_enabled": true,
      "adaptive_chunk": true,
      "min_chunk_size": 10,
      "max_chunk_size": 20,
      "target_delay": "8-12秒",
      "llm_context": {
        "history_count": 7,
        "max_tokens": 12000,
        "compression_threshold": 0.7,
        "speaker_context_duration": 600,
        "update_frequency": "batch",
        "priority_mode": "quality"
      }
    },
    "balanced": {
      "name": "バランス重視",
      "description": "精度と遅延のバランスを取る（推奨設定）",
      "chunk_size": 12,
      "buffer_size": 25,
      "overlap_size": 2.5,
      "vad_enabled": true,
      "adaptive_chunk": true,
      "min_chunk_size": 8,
      "max_chunk_size": 16,
      "target_delay": "5-8秒",
      "llm_context": {
        "history_count": 5,
        "max_tokens": 8000,
        "compression_threshold": 0.8,
        "speaker_context_duration": 300,
        "update_frequency": "adaptive",
        "priority_mode": "balanced"
      }
    },
    "low_latency": {
      "name": "低遅延優先",
      "description": "応答速度を最優先（精度は若干犠牲）",
      "chunk_size": 8,
      "buffer_size": 16,
      "overlap_size": 1.5,
      "vad_enabled": true,
      "adaptive_chunk": true,
      "min_chunk_size": 6,
      "max_chunk_size": 12,
      "target_delay": "3-5秒",
      "llm_context": {
        "history_count": 3,
        "max_tokens": 4000,
        "compression_threshold": 0.9,
        "speaker_context_duration": 180,
        "update_frequency": "immediate",
        "priority_mode": "speed"
      }
    }
  },
  "default_profile": "balanced"
}
```

### 2. 音声処理設定クラス定義
```python
# config/audio_config.py
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal

class LLMContextConfig(BaseModel):
    """LLM文脈バッファリング設定"""
    # 文脈履歴管理
    history_count: int = Field(default=5, ge=1, le=20,
                              description="翻訳履歴保持数")
    max_tokens: int = Field(default=8000, ge=2000, le=20000,
                           description="最大文脈トークン数")
    compression_threshold: float = Field(default=0.8, ge=0.5, le=0.95,
                                       description="文脈圧縮開始閾値")
    
    # 話者別設定
    speaker_context_duration: int = Field(default=300, ge=60, le=1800,
                                        description="話者別文脈保持時間（秒）")
    enable_speaker_separation: bool = Field(default=True,
                                          description="話者別文脈分離")
    
    # 更新戦略
    update_frequency: Literal["immediate", "adaptive", "batch"] = \
        Field(default="adaptive", description="文脈更新頻度")
    priority_mode: Literal["speed", "balanced", "quality"] = \
        Field(default="balanced", description="文脈優先度モード")
    
    # メモリ管理
    memory_limit_mb: int = Field(default=50, ge=10, le=200,
                                description="文脈メモリ制限（MB）")
    cleanup_interval: int = Field(default=60, ge=30, le=300,
                                 description="文脈クリーンアップ間隔（秒）")
    
    # 圧縮設定
    enable_context_compression: bool = Field(default=True,
                                           description="文脈圧縮有効化")
    compression_algorithm: Literal["summarization", "truncation", "importance"] = \
        Field(default="importance", description="圧縮アルゴリズム")
    
    @validator('max_tokens')
    def validate_token_limit(cls, v, values):
        if v < 2000:
            raise ValueError('max_tokens should be at least 2000 for meaningful context')
        return v
    
    @validator('compression_threshold')
    def validate_compression_threshold(cls, v, values):
        if 'max_tokens' in values and v * values['max_tokens'] < 1000:
            raise ValueError('Compression threshold too low - minimum context would be insufficient')
        return v

class AudioConfig(BaseModel):
    # チャンクサイズ設定
    chunk_size: float = Field(default=12.0, ge=6.0, le=20.0, 
                             description="音声チャンクサイズ（秒）")
    buffer_size: float = Field(default=25.0, ge=12.0, le=40.0,
                              description="音声バッファサイズ（秒）")
    overlap_size: float = Field(default=2.5, ge=1.0, le=5.0,
                               description="オーバーラップサイズ（秒）")
    
    # VAD設定
    vad_enabled: bool = Field(default=True, description="VAD有効化")
    silence_threshold: float = Field(default=1.5, ge=0.5, le=3.0,
                                   description="無音検出閾値（秒）")
    
    # 適応的調整設定
    adaptive_chunk: bool = Field(default=True, description="適応的チャンクサイズ調整")
    min_chunk_size: float = Field(default=6.0, ge=4.0, le=10.0,
                                 description="最小チャンクサイズ（秒）")
    max_chunk_size: float = Field(default=20.0, ge=15.0, le=30.0,
                                 description="最大チャンクサイズ（秒）")
    
    # パフォーマンスモード
    performance_mode: Literal["high_precision", "balanced", "low_latency"] = \
        Field(default="balanced", description="パフォーマンスプロファイル")
    
    @validator('buffer_size')
    def buffer_size_must_be_larger_than_chunk(cls, v, values):
        if 'chunk_size' in values and v < values['chunk_size'] * 1.5:
            raise ValueError('buffer_size must be at least 1.5x chunk_size')
        return v
    
    @validator('overlap_size')
    def overlap_size_must_be_smaller_than_chunk(cls, v, values):
        if 'chunk_size' in values and v >= values['chunk_size'] * 0.5:
            raise ValueError('overlap_size must be less than 50% of chunk_size')
        return v

class SystemConfig(BaseModel):
    # 音声設定
    audio: AudioConfig = Field(default_factory=AudioConfig)
    
    # LLM文脈設定
    llm_context: LLMContextConfig = Field(default_factory=LLMContextConfig)
    
    # デバイス設定
    input_device: Optional[int] = Field(default=None, description="入力デバイスID")
    sample_rate: int = Field(default=16000, description="サンプリングレート")
    
    # 言語設定
    source_lang: str = Field(description="発話言語")
    target_lang: str = Field(description="翻訳対象言語")
    
    # 出力設定
    speaker_name: str = Field(description="発話者名")
    google_docs_id: Optional[str] = Field(default=None, description="Google DocsドキュメントID")
    output_dir: Optional[str] = Field(default=None, description="出力ディレクトリ")
```

### 3. 動的設定変更機能
```python
# 実行時設定変更の実装例
class AudioSettingsManager:
    def __init__(self, config_path: str = "config/performance_profiles.json"):
        self.config = self.load_config(config_path)
        self.current_profile = self.config["default_profile"]
    
    def switch_profile(self, profile_name: str) -> AudioConfig:
        """パフォーマンスプロファイルの切り替え"""
        if profile_name not in self.config["profiles"]:
            raise ValueError(f"Unknown profile: {profile_name}")
        
        profile_data = self.config["profiles"][profile_name]
        return AudioConfig(**profile_data)
    
    def adjust_chunk_size(self, new_size: float) -> AudioConfig:
        """チャンクサイズのリアルタイム調整"""
        current_config = self.get_current_config()
        current_config.chunk_size = new_size
        return current_config
    
    def optimize_for_speaker_pattern(self, avg_speech_duration: float) -> AudioConfig:
        """発話パターンに基づく自動最適化"""
        if avg_speech_duration < 8:
            return self.switch_profile("low_latency")
        elif avg_speech_duration > 15:
            return self.switch_profile("high_precision")
        else:
            return self.switch_profile("balanced")

class LLMContextManager:
    def __init__(self):
        self.context_buffer = {}  # 話者別文脈バッファ
        self.token_count = 0
        self.last_cleanup = time.time()
    
    def adjust_context_size(self, new_history_count: int) -> LLMContextConfig:
        """文脈履歴サイズのリアルタイム調整"""
        current_config = self.get_current_config()
        current_config.history_count = new_history_count
        return current_config
    
    def optimize_for_api_limits(self, api_provider: str, rate_limit: int) -> LLMContextConfig:
        """API制限に基づく文脈設定最適化"""
        current_config = self.get_current_config()
        
        if api_provider == "claude":
            # Claude 3.5 Sonnet: 200k token limit
            current_config.max_tokens = min(15000, current_config.max_tokens)
        elif api_provider == "openai":
            # GPT-4o: 128k token limit  
            current_config.max_tokens = min(12000, current_config.max_tokens)
        
        # レート制限に応じた更新頻度調整
        if rate_limit < 10:
            current_config.update_frequency = "batch"
        elif rate_limit > 30:
            current_config.update_frequency = "immediate"
        else:
            current_config.update_frequency = "adaptive"
            
        return current_config
    
    def monitor_memory_usage(self) -> dict:
        """文脈バッファメモリ使用量監視"""
        total_size = sum(len(str(context)) for context in self.context_buffer.values())
        memory_mb = total_size / (1024 * 1024)
        
        return {
            "memory_usage_mb": memory_mb,
            "buffer_count": len(self.context_buffer),
            "average_context_size": total_size / max(len(self.context_buffer), 1),
            "token_count": self.token_count
        }
```

### 4. コマンドライン引数の拡張仕様
```bash
# 基本的なチャンクサイズ設定
--chunk-size FLOAT           # チャンクサイズ（秒）：6-20秒
--buffer-size FLOAT          # バッファサイズ（秒）：12-40秒
--overlap-size FLOAT         # オーバーラップサイズ（秒）：1-5秒

# プロファイル指定
--profile {high_precision,balanced,low_latency}  # 設定プリセット

# 適応的調整設定
--adaptive-chunk             # 適応的チャンクサイズ調整の有効化
--no-adaptive-chunk          # 適応的調整の無効化
--min-chunk-size FLOAT       # 最小チャンクサイズ（秒）
--max-chunk-size FLOAT       # 最大チャンクサイズ（秒）

# VAD設定
--vad / --no-vad            # VADの有効化/無効化
--silence-threshold FLOAT   # 無音検出閾値（秒）

# 実行時調整
--allow-runtime-adjustment   # 実行中の設定変更を許可
--config-file PATH          # カスタム設定ファイルパス

# LLM文脈バッファリング設定
--context-history INT       # 翻訳履歴保持数：1-20
--context-max-tokens INT    # 最大文脈トークン数：2000-20000
--context-compression FLOAT # 文脈圧縮閾値：0.5-0.95
--speaker-context-duration INT  # 話者別文脈保持時間（秒）：60-1800
--context-update-freq {immediate,adaptive,batch}  # 文脈更新頻度
--context-priority {speed,balanced,quality}       # 文脈優先度モード
--context-memory-limit INT  # 文脈メモリ制限（MB）：10-200
--no-context-compression    # 文脈圧縮の無効化
--context-algorithm {summarization,truncation,importance}  # 圧縮アルゴリズム
```

### 5. 設定の妥当性チェック機能
```python
def validate_audio_settings(config: AudioConfig) -> List[str]:
    """音声設定の妥当性をチェック"""
    warnings = []
    
    # チャンクサイズと遅延の関係
    estimated_delay = config.chunk_size + 2.0  # 処理時間の概算
    if estimated_delay > 12:
        warnings.append(f"大きなチャンクサイズ({config.chunk_size}s)により遅延が{estimated_delay:.1f}秒になる可能性があります")
    
    # メモリ使用量の推定
    estimated_memory = config.buffer_size * 16000 * 2  # 16kHz, 16bit概算
    if estimated_memory > 1024 * 1024:  # 1MB以上
        warnings.append(f"大きなバッファサイズによりメモリ使用量が約{estimated_memory/1024/1024:.1f}MB増加します")
    
    # オーバーラップと精度の関係
    overlap_ratio = config.overlap_size / config.chunk_size
    if overlap_ratio < 0.15:
        warnings.append("オーバーラップが小さすぎると文脈が失われる可能性があります")
    elif overlap_ratio > 0.4:
        warnings.append("オーバーラップが大きすぎると処理が重複し非効率です")
    
    return warnings

def validate_llm_context_settings(config: LLMContextConfig, api_provider: str = "claude") -> List[str]:
    """LLM文脈設定の妥当性をチェック"""
    warnings = []
    
    # API制限との整合性チェック
    api_limits = {
        "claude": 200000,    # Claude 3.5 Sonnet
        "openai": 128000,    # GPT-4o
        "gemini": 1000000    # Gemini Pro
    }
    
    if api_provider in api_limits and config.max_tokens > api_limits[api_provider] * 0.8:
        warnings.append(f"{api_provider} APIの制限({api_limits[api_provider]:,}トークン)に対して文脈サイズが大きすぎます")
    
    # メモリ使用量の推定
    estimated_memory = config.history_count * config.max_tokens * 4 / 1024 / 1024  # 概算（バイト→MB）
    if estimated_memory > config.memory_limit_mb:
        warnings.append(f"推定メモリ使用量({estimated_memory:.1f}MB)が制限({config.memory_limit_mb}MB)を超過する可能性があります")
    
    # 履歴数と遅延の関係
    if config.history_count > 10 and config.update_frequency == "immediate":
        warnings.append("大きな履歴数とimmediate更新モードの組み合わせは遅延を増加させる可能性があります")
    
    # 圧縮設定の整合性
    if config.enable_context_compression and config.compression_threshold > 0.9:
        warnings.append("圧縮閾値が高すぎると圧縮効果が期待できません")
    
    # 話者別文脈の設定
    if config.enable_speaker_separation and config.speaker_context_duration < 120:
        warnings.append("話者別文脈の保持時間が短すぎると文脈の一貫性が失われる可能性があります")
    
    return warnings
```

## 実装の詳細仕様

### 音声認識の高性能化（段階的最適化戦略）
- **段階的導入**: 環境に応じた最適モデル選択
  ```python
  # 実装例：条件付きモデル選択
  import platform
  
  if platform.system() == "Darwin":  # macOS
      try:
          from whisperkit import WhisperKit
          model = WhisperKit(model="large-v3")
          print("Using optimized WhisperKit (15x faster)")
      except ImportError:
          import whisper
          model = whisper.load_model("large-v3")
          print("Fallback to standard Whisper")
  else:
      import whisper
      model = whisper.load_model("large-v3")
  ```
- **パフォーマンス指標**:
  - macOS特化: 15倍高速化、19%レイテンシ改善、45%メモリ削減
  - 精度維持: WER 1.99%（標準Whisperと同等）
  - プライバシー: 完全ローカル処理（macOS特化モデル）
- **バッチ処理の最適化**: 量子化（INT4/INT8）による追加高速化

### 翻訳API
- **Claude**: claude-3-5-sonnet-20241022
- **OpenAI**: GPT-4o-turbo または GPT-4oo
- プロンプト: 文脈を考慮した自然な翻訳
- エラーハンドリング: API制限、ネットワークエラー対応
- **コメントアウト対象**: 既存の`bilingual_log_file_path`とバイリンガルファイル書き込み処理

### Google Docs出力
- リアルタイム更新: batchUpdateメソッドを使用
- フォーマット: タイムスタンプ、発話者名、原文、翻訳文
- 出力例:
```
[2025-01-01 14:05:23] 田中太郎:
原文(ja): こんにちは、今日の会議を始めましょう。
翻訳(en): Hello, let's start today's meeting.

[2025-01-01 14:05:45] John Smith:
原文(en): Thank you for organizing this meeting.
翻訳(ja): この会議を企画していただき、ありがとうございます。
```

## ファイル構成
```
audio-recognition-system/
├─ main_with_translation_and_docs.py（新規作成）
├─ .env（新規作成・APIキー管理）
├─ .env.example（新規作成・設定例）
├─ config/
│  ├─ api_config.py（新規作成・音声認識+翻訳+Google Docs設定統合）
│  ├─ audio_config.py（新規作成・チャンクサイズ等音声処理設定）
│  └─ performance_profiles.json（新規作成・設定プリセット管理）
├─ recognition/
│  └─ optimized_speech_recognition.py（新規作成・macOS特化+フォールバック）
├─ translation/
│  ├─ translator.py（既存・修正）
│  └─ api_translator.py（新規作成）
├─ output/
│  └─ google_docs_writer.py（新規作成）
├─ requirements.txt（更新・macOS特化モデル依存関係追加）
└─ README.md（更新・パフォーマンス向上説明追加）
```

## エラーハンドリング要件
- 翻訳API制限時の再試行機能
- 翻訳APIプロバイダー間のフォールバック機能
- Google Docs API接続エラー時のローカル保存（原文・翻訳文の最小限バックアップ）
- 音声認識失敗時のスキップ機能
- ネットワーク断絶時の復旧機能

## セキュリティ要件
- APIキーの`.env`ファイル管理（`.gitignore`に追加必須）
- `.env.example`ファイルでの設定例提供
- Google OAuth認証の適切な実装
- ログファイルでの機密情報の除外

## テスト要件
- 各APIの接続テスト機能
- 音声デバイスの動作確認機能
- エンドツーエンドのテストシナリオ

## 実装時の注意点
1. **技術選択の妥当性**
   - Python継続による既存資産活用を最優先
   - JavaScript/Node.js移行は開発工数2-3倍増のためNG
   - Google API連携の設定複雑さは両言語で同等
2. **音声認識の最適化戦略**
   - macOS環境では特化モデル優先使用（15倍高速化実現）
   - 段階的フォールバック機能でクロスプラットフォーム対応維持
   - 精度維持（WER 1.99%）しつつパフォーマンス大幅向上
   - 量子化による追加最適化（INT4推奨）
3. 既存のコードとの互換性を保持
4. 段階的な実装（最適化音声認識→翻訳→Google Docs出力）
5. パフォーマンスの最適化（特にリアルタイム性）
   - **音声認識高速化**: macOS特化モデルによる19%レイテンシ改善
   - **メモリ効率化**: 45%メモリ削減による安定動作
   - バイリンガルローカルファイル出力の削除（冗長な処理を排除）
   - ファイルI/O処理の最小化
   - Google Docs出力への集中
   - **目標遅延**: macOS特化モデル使用時3-5秒（従来10秒から短縮）
6. ユーザビリティの向上（設定の簡素化）
7. 音声デバイスの柔軟な対応
   - ヘッドセットマイク使用時の高音質・ノイズ軽減効果を活用
   - 内蔵マイク使用時の環境音対策を考慮
   - `list_audio_devices.py`を使用したデバイス確認機能の提供
8. セキュリティ設定の徹底
   - `.env`ファイルを`.gitignore`に追加
   - `.env.example`でユーザーガイダンスを提供
   - APIキーの直接コード埋め込みを禁止
9. Google Docs API実装の要点
   - `google-api-python-client`の最新版（v2.170.0以降）を使用
   - OAuth 2.0認証の適切な実装（credentials.json + token.json管理）
   - エラーハンドリング（HttpError, RefreshError対応）
   - 適切なスコープ設定（documents.readonly + documents）
10. 出力の最適化
    - **既存のバイリンガルファイル出力処理をコメントアウト**（Google Docsで統合管理）
    - `bilingual_translation_log_*.txt`の生成を一時停止
    - `bilingual_texts`配列の作成処理をコメントアウト
    - 将来的に必要に応じて復活可能な形で保持
    - エラー時のみ最小限のローカルバックアップを実行
    - 10秒以内の遅延要件を満たすための処理軽量化

このプロンプトに基づいて、実用的で高品質なオンライン会議支援システムを実装してください。 