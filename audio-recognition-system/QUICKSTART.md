# 🚀 MVP版クイックスタートガイド

オンライン会議用リアルタイム音声認識・翻訳・Google Docs出力システムを**5分で構築**

## 📋 前提条件
- **macOS** (Apple Silicon推奨)
- **Python 3.8+**
- **マイク** (ヘッドセット推奨)
- **インターネット接続**

## ⚡ 3ステップセットアップ

### 1️⃣ 自動セットアップ実行
```bash
# リポジトリディレクトリに移動
cd audio-recognition-system

# セットアップスクリプトを実行可能にして実行
chmod +x setup_mvp.sh
./setup_mvp.sh
```

### 2️⃣ APIキー設定
```bash
# 対話形式でAPIキーを設定（推奨）
./setup_api_keys.sh

# または手動設定
# 1. Claude APIキーを取得: https://console.anthropic.com/
# 2. .envファイルを編集: nano .env
# 3. CLAUDE_API_KEY=your_actual_api_key_here に変更
```

### 3️⃣ 動作確認
```bash
# 仮想環境が未アクティブの場合
source venv_mvp/bin/activate

# 環境確認
python check_environment.py

# システムテスト実行
python main_mvp.py --source-lang ja --target-lang en --speaker-name "テストユーザー"
```

## 🎯 基本的な使用例

### 日本語→英語翻訳
```bash
python main_mvp.py \
  --source-lang ja \
  --target-lang en \
  --speaker-name "田中太郎"
```

### 英語→日本語翻訳
```bash
python main_mvp.py \
  --source-lang en \
  --target-lang ja \
  --speaker-name "John Smith"
```

### Google Docsへの出力
```bash
# Google Docsドキュメントを作成してIDを取得
# https://docs.google.com/

python main_mvp.py \
  --source-lang ja \
  --target-lang en \
  --speaker-name "田中太郎" \
  --google-docs-id "YOUR_DOCUMENT_ID"
```

## 🔧 トラブルシューティング

### ❌ セットアップエラー
```bash
# 環境確認スクリプトで詳細チェック
python check_environment.py --verbose

# セットアップ検証
python test_setup.py

# セットアップ再実行
./setup_mvp.sh

# 手動でパッケージインストール（最後の手段）
source venv_mvp/bin/activate
pip install anthropic google-api-python-client pyaudio torch mlx-whisper
```

### ❌ 音声デバイスエラー
```bash
# 利用可能なデバイス確認
python list_audio_devices.py

# 特定デバイス指定
python main_mvp.py --input-device 0 --source-lang ja --target-lang en --speaker-name "テスト"
```

### ❌ API接続エラー
```bash
# APIキー確認
grep CLAUDE_API_KEY .env

# API接続テスト
python check_environment.py --api-test
```

## 📊 期待される性能

| 項目 | MVP版 | 理想版 |
|------|-------|--------|
| **遅延** | 3-5秒 | 2-3秒 |
| **音声認識** | MLX Whisper (3-10倍高速) | WhisperKit (15倍高速) |
| **翻訳品質** | 単発翻訳 | 文脈保持翻訳 |
| **対応言語** | 7言語 | 7言語+ |

## 🎉 成功確認

以下が全て動作すれば成功です：

- ✅ システム起動（エラーなし）
- ✅ 音声キャプチャ開始
- ✅ 音声認識結果表示
- ✅ Claude翻訳実行
- ✅ コンソールまたはGoogle Docsに出力
- ✅ Ctrl+Cで正常終了

## 📖 詳細情報

- **完全ガイド**: [SETUP_GUIDE.md](SETUP_GUIDE.md)
- **環境確認**: `python check_environment.py`
- **ステータス**: [MVP_TEST_STATUS.md](MVP_TEST_STATUS.md)

## 🆘 サポート

問題が発生した場合：

1. **環境確認**: `python check_environment.py --verbose`
2. **セットアップガイド確認**: [SETUP_GUIDE.md](SETUP_GUIDE.md)
3. **ログ確認**: `logs/`ディレクトリ内のファイル
4. **イシュー報告**: エラーメッセージ・実行コマンド・環境情報を含める

---

💡 **ヒント**: 初回実行時は音声認識モデルのダウンロードで数分かかる場合があります
