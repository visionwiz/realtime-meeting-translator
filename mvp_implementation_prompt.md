# オンライン会議用リアルタイム音声認識・翻訳・Google Docs出力システム - MVP版

## システム概要
既存のaudio-recognition-systemを基盤として、オンライン会議での個人発話を対象とした基本的な音声認識・翻訳・Google Docs出力システムのMVP（Minimum Viable Product）を実装します。

## MVP戦略
**「まず動かす、後で最適化する」**
- 複雑な最適化機能は後回し
- 標準的なライブラリで確実な動作を優先
- シンプルな設定で運用開始
- 動作確認後に理想の実装（implementation_prompt.md）へ移行

## 技術選択（MVP版）
**言語: Python継続**
- 既存システム活用による開発期間短縮
- Google API対応の`google-api-python-client`使用

**音声認識: 標準Whisper**
- macOS特化モデル（WhisperKit）は理想版で実装
- OpenAI Whisper large-v3で安定動作を確保
- クロスプラットフォーム対応

**翻訳: Claude 3.7 Sonnet固定**
- Claude 3.7 Sonnet（claude-3-7-sonnet-20250219）に固定
- 複雑な文脈バッファリングは後回し

## MVPの基本要件
1. 音声を文字起こし（日本語・英語対応）
2. 文字起こし結果を翻訳
3. Google Docsに発話者別で出力
4. 20秒程度の遅延は許容（最適化は後回し）

## 技術仕様（MVP版）

### 音声入力
- **入力デバイス**: デフォルトマイクまたはコマンドライン指定
- **音声形式**: 16kHz, モノラル
- **対象音声**: 利用者自身の発話

### 音声認識
- **モデル**: OpenAI Whisper large-v3
- **言語指定**: コマンドライン引数で指定
- **チャンクサイズ**: 固定10秒（最適化は理想版で実装）

### 翻訳
- **API**: Claude 3.7 Sonnet（claude-3-7-sonnet-20250219）固定
- **翻訳方向**: 発話言語→対象言語（コマンドライン指定）
- **文脈**: シンプルな単発翻訳（文脈バッファリングは後回し）

### Google Docs出力
- **技術**: `google-api-python-client`
- **認証**: OAuth 2.0
- **出力形式**: タイムスタンプ + 発話者名 + 原文 + 翻訳文
- **更新頻度**: 翻訳完了毎に追記

## 実装要件（MVP版）

### 1. ファイル構成（最小限）
```
audio-recognition-system/
├─ main_mvp.py（新規作成・メインスクリプト）
├─ .env（新規作成）
├─ .env.example（新規作成）
├─ config/
│  └─ mvp_config.py（新規作成・シンプルな設定管理）
├─ translation/
│  └─ claude_translator.py（新規作成・Claude 3.7 Sonnet翻訳）
├─ output/
│  └─ basic_google_docs_writer.py（新規作成・基本的な出力）
├─ requirements_mvp.txt（新規作成）
└─ README_MVP.md（新規作成）
```

### 2. 依存関係（最小限）
```
# requirements_mvp.txt
# 音声認識
openai-whisper>=20231117

# 翻訳API（Claude 3.7 Sonnet固定）
anthropic>=0.25.0          # Claude API用

# Google Docs API
google-api-python-client>=2.170.0
google-auth-httplib2>=0.2.0
google-auth-oauthlib>=1.0.0
google-auth>=2.0.0

# 基本的な音声処理
pyaudio>=0.2.11
sounddevice>=0.4.6

# 設定管理
python-dotenv>=1.0.0
```

### 3. 環境変数設定（簡素化）
```bash
# .env ファイルの例（MVP版）
# 翻訳API（Claude 3.7 Sonnet固定）
CLAUDE_API_KEY=your_claude_api_key_here
CLAUDE_MODEL_NAME=claude-3-7-sonnet-20250219

# Google Docs API
GOOGLE_DOCS_CREDENTIALS_PATH=path/to/credentials.json
GOOGLE_DOCS_TOKEN_PATH=path/to/token.json

# 音声設定（固定値）
AUDIO_CHUNK_SIZE=10  # 固定10秒
AUDIO_SAMPLE_RATE=16000
```

### 4. コマンドライン引数（簡素化）
```bash
# MVP版の基本的な使用例
python main_mvp.py \
  --source-lang ja \
  --target-lang en \
  --speaker-name "田中太郎" \
  --google-docs-id "YOUR_DOCUMENT_ID"

# 入力デバイス指定（オプション）
python main_mvp.py \
  --input-device 1 \
  --source-lang en \
  --target-lang ja \
  --speaker-name "John Smith" \
  --google-docs-id "YOUR_DOCUMENT_ID"
```

### 5. 基本設定クラス（MVP版）
```python
# config/mvp_config.py
from dataclasses import dataclass
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

@dataclass
class MVPConfig:
    # 言語設定
    source_lang: str
    target_lang: str
    speaker_name: str
    
    # デバイス設定
    input_device: Optional[int] = None
    sample_rate: int = 16000
    chunk_size: int = 10  # 固定10秒
    
    # Claude API設定（固定）
    claude_api_key: Optional[str] = os.getenv("CLAUDE_API_KEY")
    claude_model_name: str = os.getenv("CLAUDE_MODEL_NAME", "claude-3-7-sonnet-20250219")
    
    # Google Docs設定
    google_docs_id: Optional[str] = None
    google_credentials_path: str = os.getenv("GOOGLE_DOCS_CREDENTIALS_PATH", "credentials.json")
    google_token_path: str = os.getenv("GOOGLE_DOCS_TOKEN_PATH", "token.json")
    
    def validate(self):
        """基本的な設定検証"""
        if not self.source_lang or not self.target_lang:
            raise ValueError("発話言語と翻訳言語を指定してください")
        
        if not self.speaker_name:
            raise ValueError("発話者名を指定してください")
        
        if not self.claude_api_key:
            raise ValueError("Claude APIキーが設定されていません")
```

## 理想版への移行パス

### MVPで検証すべき項目
1. 音声認識の基本精度
2. 翻訳品質の評価
3. Google Docs出力の安定性
4. 全体的な使用感とワークフロー
5. エラー発生パターンの特定

### 理想版で追加する機能
1. **音声認識最適化**
   - macOS特化モデル（WhisperKit）導入
   - 15倍高速化、19%レイテンシ改善
   - チャンクサイズ最適化

2. **翻訳品質向上**
   - LLM文脈バッファリング
   - 適応的翻訳戦略
   - 話者別文脈保持

3. **パフォーマンス最適化**
   - 適応的調整機能
   - パフォーマンスプロファイル
   - メモリ効率化

4. **運用機能強化**
   - 段階的フォールバック
   - 高度なエラーハンドリング
   - モニタリング機能

## エラーハンドリング（MVP版）
- API接続エラー時の基本的な再試行
- 音声認識失敗時のスキップ
- Google Docs接続エラー時のコンソール出力
- 致命的エラー時の適切な終了

## セキュリティ要件（MVP版）
- `.env`ファイルでのAPIキー管理
- `.gitignore`への`.env`追加
- Google OAuth認証の基本実装

## 成功判定基準
- 10分間の会議で音声認識・翻訳・Google Docs出力が継続動作
- 翻訳精度が実用レベル（文意が伝わる程度）
- システムクラッシュなしでの安定動作
- ユーザーが基本操作を理解できること

## 次ステップ
MVPテスト運用完了後、以下の順序で理想版に移行：
1. 音声認識最適化（macOS特化モデル導入）
2. 翻訳品質向上（文脈バッファリング）
3. パフォーマンス最適化（チャンクサイズ調整）
4. 運用機能強化（監視・エラーハンドリング）

このMVP実装により、まずは確実に動作するシステムを構築し、ユーザーフィードバックを得てから理想の実装に進む戦略を採用します。 