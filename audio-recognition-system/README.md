# シンプル版 リアルタイム音声認識・翻訳・Google Docs出力システム

## 概要
オンライン会議での個人発話を対象とした、音声認識→Claude翻訳→Google Docs出力の統合システムです。

**設計方針**: StreamingRecognize前提で設計された軽量実装、無音自動一時停止機能付き

## 🚀 クイックスタート（新規ユーザー向け）

### 5分で環境構築
```bash
# 1. 自動セットアップ実行
chmod +x setup_mvp.sh && ./setup_mvp.sh

# 2. 環境確認
python check_environment.py

# 3. セットアップ検証
python test_setup.py
```

**詳細手順**: [QUICKSTART.md](QUICKSTART.md) | **完全ガイド**: [SETUP_GUIDE.md](SETUP_GUIDE.md)

## 機能
- ✅ **音声認識**: Google Cloud Speech V2（ストリーミング特化・高速）
- ✅ **翻訳**: Claude 3.7 Sonnetによる自然な翻訳
- ✅ **Google Docs出力**: リアルタイムでの会議記録自動生成
- ✅ **Google Docsタブ対応**: ドキュメント内の特定タブへの出力機能
- ✅ **多言語対応**: 日本語・英語・韓国語・中国語・スペイン語・フランス語・ドイツ語
- ✅ **自動セットアップ**: ワンクリック環境構築
- ✅ **無音自動一時停止**: 継続的ストリーミング機能
- ✅ **録音データテスト**: 音声ファイルでのシステム評価機能

## システム要件
- Python 3.8+
- macOS (推奨) / Windows / Linux
- マイク（ヘッドセット推奨）
- インターネット接続

## 📁 プロジェクト構成

### 🔧 環境構築ツール
| ファイル | 説明 | 使用方法 |
|----------|------|----------|
| `setup_mvp.sh` | 自動セットアップスクリプト | `chmod +x setup_mvp.sh && ./setup_mvp.sh` |
| `setup_api_keys.sh` | APIキー設定支援スクリプト | `chmod +x setup_api_keys.sh && ./setup_api_keys.sh` |
| `check_environment.py` | 環境確認・診断ツール | `python check_environment.py --verbose` |
| `test_setup.py` | セットアップ検証ツール | `python test_setup.py --full` |

### 📚 ドキュメント
| ファイル | 内容 | 対象者 |
|----------|------|--------|
| `QUICKSTART.md` | 5分構築ガイド | 新規ユーザー |
| `SETUP_GUIDE.md` | 詳細セットアップ手順 | 全ユーザー |
| `MVP_TEST_STATUS.md` | 現在のセットアップ状況 | 開発者・管理者 |

### ⚙️ 依存関係ファイル
| ファイル | 説明 | 使用場面 |
|----------|------|----------|
| `requirements.txt` | 動作確認済み依存関係（固定バージョン） | 通常セットアップ・問題発生時の復旧 |

### 🎯 システム構成
| ディレクトリ/ファイル | 説明 |
|-------------------|------|
| `main.py` | メインシステム（シンプル版統合スクリプト） |
| `config/mvp_config.py` | 設定管理クラス |
| `translation/claude_translator.py` | Claude 3.7 Sonnet翻訳エンジン |
| `output/basic_google_docs_writer.py` | Google Docs出力エンジン |
| `recognition/simple_speech_recognition.py` | Google Cloud Speech V2ストリーミング認識 |
| `audio/simple_capture.py` | シンプル音声キャプチャ |
| `audio/file_audio_capture.py` | 録音ファイル対応音声キャプチャ |
| `evaluate_transcription.py` | 音声認識精度評価ツール |
| `test_data/` | 録音データテスト用ファイル（音声・正解データ） |

## 🎵 録音データテスト機能

録音済み音声ファイルを使用してシステムの音声認識精度や安定性を評価できます。

### 📁 テストデータ構成
```
test_data/
├── audio/リアルタイムミーティング翻訳検証音声データ.mp3  # 約70秒の日本語音声
└── reference/リアルタイムミーティング翻訳検証音声データ_正解データ.txt  # 正解文字起こし
```

### 🚀 クイックテスト
```bash
# 最速テスト（25秒で完了）
python main.py \
  --audio-file "test_data/audio/リアルタイムミーティング翻訳検証音声データ.mp3" \
  --source-lang ja \
  --target-lang en \
  --transcription-only \
  --playback-speed 3.0

# 精度評価（自動WER計算）
python evaluate_transcription.py \
  "test_data/reference/リアルタイムミーティング翻訳検証音声データ_正解データ.txt" \
  "logs/simple_transcription_ja_YYYYMMDD_HHMMSS.txt" \
  --verbose
```

### 📊 対応フォーマット・オプション
- **音声形式**: MP3 ✅ WAV ✅ FLAC ✅ M4A ✅ OGG ✅
- **再生速度**: `--playback-speed 1.0`（リアルタイム）〜 `3.0`（3倍速）
- **評価指標**: WER (Word Error Rate)、認識精度、完了率

詳細は [`test_data/README.md`](test_data/README.md) を参照してください。

## セットアップ

### 自動セットアップ（推奨）
```bash
# 1. 依存関係の自動セットアップ
./setup_mvp.sh

# 2. APIキーの設定
./setup_api_keys.sh

# 3. セットアップ後の確認
python check_environment.py
python test_setup.py
```

### 手動セットアップ
```bash
# 1. 仮想環境作成・有効化
python3 -m venv venv_mvp
source venv_mvp/bin/activate

# 2. 依存関係インストール（動作確認済みバージョン）
pip install -r requirements.txt

# 3. Pythonパッケージ構造修正
touch translation/__init__.py output/__init__.py
rm -f config/__init__.py
```

### 2. Claude APIキーの取得
1. [Anthropic Console](https://console.anthropic.com/) にアクセス
2. アカウント作成・ログイン
3. APIキーを作成
4. 後の環境変数設定で使用

### 3. Google Docs API設定
1. [Google Cloud Console](https://console.cloud.google.com/) にアクセス
2. 新しいプロジェクト作成または既存選択
3. **Google Docs API**を有効化
4. **OAuth 2.0 認証情報**を作成
   - アプリケーションタイプ: デスクトップアプリケーション
5. `credentials.json`をダウンロード
6. プロジェクトルートに配置

### 4. 環境変数設定
プロジェクトルートに`.env`ファイルを作成：

```bash
# .env ファイル
# Claude API設定（必須）
CLAUDE_API_KEY=your_claude_api_key_here
CLAUDE_MODEL_NAME=claude-3-7-sonnet-20250219

# Google Docs API設定
GOOGLE_DOCS_CREDENTIALS_PATH=credentials.json
GOOGLE_DOCS_TOKEN_PATH=token.json
GOOGLE_DOCS_TAB_ID=t.0-0

# 音声設定（オプション）
AUDIO_CHUNK_SIZE=10
AUDIO_SAMPLE_RATE=16000
LOG_LEVEL=INFO
```

### 5. .gitignoreの更新
セキュリティ確保のため、以下を`.gitignore`に追加：
```
.env
credentials.json
token.json
```

## 使用方法

### 基本的な使用
```bash
# 音声認識・翻訳・Google Docs出力
python main.py \
  --source-lang ja \
  --target-lang en \
  --google-docs-id "YOUR_DOCUMENT_ID"
```

### 発話捕捉率テスト（推奨）
```bash
# 音声認識のみ（最高速・リソース節約）
python main.py \
  --source-lang ja \
  --target-lang en \
  --transcription-only

# 翻訳無効化（Google Docs出力のみ有効）
python main.py \
  --source-lang ja \
  --target-lang en \
  --google-docs-id "YOUR_DOCUMENT_ID" \
  --disable-translation

# Google Docs出力無効化（翻訳のみ有効）
python main.py \
  --source-lang ja \
  --target-lang en \
  --disable-docs-output
```

### Google Docs出力付き
```bash
# 1. Google Docsで新しいドキュメントを作成
# 2. URLからドキュメントIDを取得（例: 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms）
# 3. 実行

python main.py \
  --source-lang ja \
  --target-lang en \
  --google-docs-id "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
```

### Google Docsタブ指定出力
```bash
# Google Docsドキュメント内の特定のタブに出力
# タブIDは以下の方法で取得可能：
# 1. Google DocsでタブのURLを確認（例: /edit#tab=t.0-0）
# 2. タブIDは「t.0-0」の部分

python main.py \
  --source-lang ja \
  --target-lang en \
  --google-docs-id "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms" \
  --google-docs-tab-id "t.0-0"
```

### デバイス指定
```bash
# 音声デバイス確認
python list_audio_devices.py

# 特定デバイス使用（OpenComm by Shokz推奨）
python main.py \
  --input-device 0 \
  --source-lang en \
  --target-lang ja \
  --google-docs-id "YOUR_DOCUMENT_ID"
```

## コマンドライン引数

### 必須引数
- `--source-lang`: 発話言語 (ja, en, ko, zh, es, fr, de)
- `--target-lang`: 翻訳先言語 (ja, en, ko, zh, es, fr, de)

### オプション引数
- `--input-device`: 音声入力デバイスのインデックス
- `--model`: 音声認識モデル (tiny, base, small, medium, large-v2, large-v3)
- `--google-docs-id`: Google DocsドキュメントID
- `--google-docs-tab-id`: Google DocsタブID（オプション）
- `--output-dir`: ログ出力ディレクトリ
- `--audio-file`: 録音済み音声ファイルのパス（録音データテスト用）
- `--playback-speed`: 録音ファイル再生速度倍率（デフォルト: 1.0）

### 機能無効化オプション
- `--disable-translation`: 翻訳機能を無効化（音声認識のみ実行）
- `--disable-docs-output`: Google Docs出力を無効化
- `--transcription-only`: 音声認識のみ実行（翻訳・出力を無効化）

## 推奨デバイス設定

### 🎧 音声入力デバイス
| デバイス | ステータス | 備考 |
|---------|-----------|------|
| **OpenComm by Shokz (Device 0)** | ✅ **推奨** | 完璧な音声分離、他の参加者音声除外 |
| **MacBook Air内蔵マイク** | ⚠️ **代替案** | 環境音混入の可能性 |
| **BlackHole 2ch** | ❌ **非推奨** | システム音声混入 |

### 📋 Google Docsドキュメントの準備
1. Google Docsで新しいドキュメント作成
2. 共有設定で「リンクを知っている全員が編集可」に設定（推奨）
3. URLの`/d/`と`/edit`の間の文字列がドキュメントID

### 📑 Google Docsタブ機能（NEW）

Google Docsの新しいタブ機能を活用して、ドキュメント内の特定のタブに翻訳結果を出力できます。

#### タブIDの取得方法
1. Google Docsでタブを作成後、そのタブをクリック
2. ブラウザのURLを確認（例: `https://docs.google.com/document/d/DOCUMENT_ID/edit#tab=t.0-0`）
3. `#tab=`以降の文字列がタブID（例: `t.0-0`）

#### タブ機能の利点
- **会議の構造化**: 議題別・話者別にタブを分けて整理
- **多言語対応**: 言語別にタブを分けて同時出力
- **進行管理**: 会議の進行に合わせてタブを切り替え

#### 使用例
```bash
# 日本語話者用タブ（t.0-0）に出力
python main.py \
  --source-lang ja \
  --target-lang en \
  --google-docs-id "YOUR_DOCUMENT_ID" \
  --google-docs-tab-id "t.0-0"

# 英語話者用タブ（t.0-1）に出力  
python main.py \
  --source-lang en \
  --target-lang ja \
  --google-docs-id "YOUR_DOCUMENT_ID" \
  --google-docs-tab-id "t.0-1"
```

#### 注意事項
- タブ機能はGoogle Workspace有料プランでのみ利用可能
- タブIDが指定されていない場合は、従来通りドキュメントの最初のタブに出力
- 存在しないタブIDを指定した場合はエラーが発生

#### タブ機能テスト
```bash
# タブ機能が正しく動作するかテスト
python test_docs_tabs.py YOUR_DOCUMENT_ID t.0-0

# デフォルトタブのテスト
python test_docs_tabs.py YOUR_DOCUMENT_ID
```

## 出力形式

### Google Docs出力例
```
=== リアルタイム会議翻訳セッション開始 ===
開始時刻: 2025-01-01 14:05:00
翻訳方向: ja → en
=======================================

[2025-01-01 14:05:23] 発話者:
原文(ja): こんにちは、今日の会議を始めましょう。
翻訳(en): Hello, let's start today's meeting.

[2025-01-01 14:05:45] 発話者:
原文(ja): ありがとうございます。
翻訳(en): Thank you.
```

## トラブルシューティング

### Claude API接続エラー
```bash
❌ Claude API接続に失敗しました
```
- APIキーが正しく設定されているか確認
- インターネット接続を確認
- API制限に達していないか確認

### Google Docs API認証エラー
```bash
❌ Google Docs API接続に失敗しました
```
- `credentials.json`が正しく配置されているか確認
- Google Docs APIが有効化されているか確認
- 初回実行時はブラウザで認証が必要

### 音声認識エラー
```bash
❌ 音声デバイスが見つかりません
```
- `python list_audio_devices.py`でデバイス確認
- マイクの接続とアクセス許可を確認
- macOSの場合、システム環境設定でマイクアクセスを許可

## パフォーマンス

### シンプル版の想定性能
- **音声認識遅延**: 2-3秒（ストリーミング特化）
- **翻訳遅延**: 3-5秒
- **Google Docs出力**: 1-2秒
- **総遅延**: 6-10秒（高速化実現）

### リソース使用量
- **メモリ**: 500MB-1GB（軽量実装）
- **CPU**: 低程度（ストリーミング最適化）
- **ネットワーク**: 翻訳・Google Docs API呼び出し時のみ

## 成功判定基準
- ✅ 30分間の継続動作（無音自動一時停止機能）
- ✅ 翻訳内容が実用レベル
- ✅ Google Docsへの正常出力
- ✅ システムクラッシュなし
- ✅ Googleタイムアウト制限の自動回避

## 今後の拡張予定
システム検証完了後、以下の機能を追加予定：
1. **音声認識最適化**: macOS特化モデル（15倍高速化）
2. **翻訳品質向上**: 文脈バッファリング
3. **パフォーマンス最適化**: 1-2秒遅延目標
4. **運用機能強化**: 詳細監視・エラーハンドリング

## ライセンス
MIT License

## サポート
- 問題報告: GitHubのIssues
- ドキュメント: README.md参照
- 開発情報: main.pyのコメント参照 