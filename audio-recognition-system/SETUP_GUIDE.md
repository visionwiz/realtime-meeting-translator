# MVP版セットアップガイド

## システム概要
オンライン会議用リアルタイム音声認識・翻訳・Google Docs出力システムのMVP版です。

**機能**:
- 音声認識（日本語・英語対応）
- Claude 3.7 Sonnetによる高品質翻訳
- Google Docsへのリアルタイム出力

## 前提条件
- macOS (Apple Silicon推奨)
- Python 3.8以上
- マイク（ヘッドセット推奨）

## 1. 依存関係インストール

### 1.1 仮想環境の作成・有効化
```bash
# プロジェクトディレクトリに移動
cd audio-recognition-system

# 仮想環境作成
python3 -m venv venv_mvp

# 仮想環境有効化
source venv_mvp/bin/activate
```

### 1.2 必須パッケージのインストール
```bash
# 基本パッケージ
python -m pip install --upgrade pip

# API関連パッケージ（優先インストール）
pip install anthropic
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib google-auth
pip install python-dotenv

# 音声処理パッケージ
pip install pyaudio sounddevice

# 機械学習・音声認識パッケージ
pip install torch transformers accelerate

# macOS最適化パッケージ（条件付き）
pip install mlx-lm mlx-whisper  # macOSの場合のみ

# Whisperのインストール（問題がある場合は別途対応）
pip install openai-whisper
```

## 2. API設定

### 2.1 Claude API設定
1. [Anthropic Console](https://console.anthropic.com/)にアクセス
2. APIキーを取得
3. `.env`ファイルを作成：
```bash
cp .env.example .env
```
4. `.env`ファイルの`CLAUDE_API_KEY`に実際のAPIキーを設定

### 2.2 Google Docs API設定
1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. 新しいプロジェクト作成または既存プロジェクト選択
3. Google Docs APIを有効化
4. 認証情報（OAuth 2.0クライアントID）を作成
5. `credentials.json`をダウンロードしてプロジェクトルートに配置

### 2.3 Google Docsドキュメント準備
1. Google Docsで新しいドキュメントを作成
2. URLからドキュメントIDを取得（例：`1abcdefg...`の部分）
3. ドキュメントの共有設定で編集権限を確認

## 3. 音声デバイス確認
```bash
# 利用可能な音声デバイス一覧表示
python list_audio_devices.py
```

## 4. 接続テスト

### 4.1 インポートテスト
```bash
# 基本的なインポートテスト
python -c "import anthropic, google.auth; print('✅ API関連パッケージ正常')"
```

### 4.2 Claude APIテスト
```bash
# Claude翻訳テスト
python -c "
from translation.claude_translator import ClaudeTranslator
import os
from dotenv import load_dotenv
load_dotenv()
translator = ClaudeTranslator(os.getenv('CLAUDE_API_KEY'), 'claude-3-7-sonnet-20250219')
print('Claude API:', '✅ 接続成功' if translator.test_connection() else '❌ 接続失敗')
"
```

### 4.3 Google Docs APIテスト
```bash
# 既存のテストスクリプト実行
python test_google_docs_simple.py
```

## 5. MVP版システム実行

### 5.1 基本的な実行例
```bash
# 日本語→英語翻訳
python main_mvp.py \
  --source-lang ja \
  --target-lang en \
  --speaker-name "田中太郎" \
  --google-docs-id "YOUR_DOCUMENT_ID"

# 英語→日本語翻訳
python main_mvp.py \
  --source-lang en \
  --target-lang ja \
  --speaker-name "John Smith" \
  --google-docs-id "YOUR_DOCUMENT_ID"
```

### 5.2 ヘッドセット使用例
```bash
# 入力デバイス指定（デバイス0を使用）
python main_mvp.py \
  --input-device 0 \
  --source-lang ja \
  --target-lang en \
  --speaker-name "田中太郎" \
  --google-docs-id "YOUR_DOCUMENT_ID"
```

## 6. 動作確認項目
- [ ] 音声キャプチャが正常に動作する
- [ ] 音声認識結果がコンソールに表示される
- [ ] Claude翻訳が実行される
- [ ] Google Docsに結果が出力される
- [ ] Ctrl+Cで正常終了できる

## 7. トラブルシューティング

### 7.1 依存関係エラー
```bash
# openai-whisperのインストールエラーの場合
pip install --upgrade setuptools wheel
pip install openai-whisper --no-build-isolation
```

### 7.2 音声デバイスエラー
```bash
# pyaudioのインストールエラー（macOS）
brew install portaudio
pip install pyaudio
```

### 7.3 API接続エラー
- Claude API: APIキーが正しく設定されているか確認
- Google Docs API: `credentials.json`が正しく配置されているか確認
- ネットワーク接続を確認

### 7.4 権限エラー
```bash
# マイクアクセス許可が必要な場合
# システム環境設定 > セキュリティとプライバシー > プライバシー > マイク
```

## 8. 既知の制限事項
- **遅延**: 3-5秒（音声認識+翻訳+出力）
- **文脈**: 単発翻訳（会話の流れは考慮されない）
- **言語**: 主要7言語のみ対応
- **チャンクサイズ**: 固定10秒（調整不可）

## 9. 次のステップ
MVP版テスト成功後、理想版への移行を検討：
- WhisperKit導入（macOS特化高速化）
- LLM文脈バッファリング（翻訳品質向上）
- 適応的チャンクサイズ調整
- パフォーマンスプロファイル

## サポート
問題が発生した場合は、以下の情報を含めてレポートしてください：
- エラーメッセージ
- 実行コマンド
- 環境情報（OS、Python版）
- ログファイル（`logs/`ディレクトリ内） 