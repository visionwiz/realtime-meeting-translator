# テストデータ

リアルタイムミーティング翻訳システムの音声認識精度評価用のテストデータセットです。

## 📁 ディレクトリ構成

```
test_data/
├── audio/                                    # 音声ファイル
│   └── リアルタイムミーティング翻訳検証音声データ.mp3
├── reference/                                # 正解データ
│   └── リアルタイムミーティング翻訳検証音声データ_正解データ.txt
└── README.md                                # このファイル
```

## 🎵 音声ファイル

### `リアルタイムミーティング翻訳検証音声データ.mp3`
- **形式**: MP3
- **時間**: 約70秒
- **内容**: 保育ICTサービスの説明（日本語）
- **話者**: 1名
- **品質**: 高品質録音（ノイズ除去済み）

**特徴**:
- 実際のプレゼンテーション音声を録音
- 業務用語・専門用語を含む実用的な内容
- 自然な発話速度とイントネーション

## 📝 正解データ

### `リアルタイムミーティング翻訳検証音声データ_正解データ.txt`
- **形式**: タイムスタンプ付きテキスト
- **発話数**: 11発話
- **タイムスタンプ**: 発話開始時間（00:00:01〜00:01:06）

**フォーマット**:
```
[HH:MM:SS] 発話内容
```

**例**:
```
[00:00:01] 写真管理の自動化をします。
[00:00:07] iPhone ipadで撮影した写真が自動でクラウドにアップロード。
```

## 🧪 使用方法

### 1. 録音データでの音声認識テスト

```bash
# 基本テスト（音声認識のみ、高速）
python main.py \
  --audio-file "test_data/audio/リアルタイムミーティング翻訳検証音声データ.mp3" \
  --source-lang ja \
  --target-lang en \
  --speaker-name "テストユーザー" \
  --transcription-only

# 高速テスト（3倍速再生）
python main.py \
  --audio-file "test_data/audio/リアルタイムミーティング翻訳検証音声データ.mp3" \
  --source-lang ja \
  --target-lang en \
  --speaker-name "テストユーザー" \
  --transcription-only \
  --playback-speed 3.0
```

### 2. 翻訳機能付きテスト

```bash
# 翻訳テスト
python main.py \
  --audio-file "test_data/audio/リアルタイムミーティング翻訳検証音声データ.mp3" \
  --source-lang ja \
  --target-lang en \
  --speaker-name "テストユーザー" \
  --disable-docs-output
```

### 3. Google Docs出力テスト

```bash
# 完全機能テスト
python main.py \
  --audio-file "test_data/audio/リアルタイムミーティング翻訳検証音声データ.mp3" \
  --source-lang ja \
  --target-lang en \
  --speaker-name "テストユーザー" \
  --google-docs-id "YOUR_DOCS_ID"
```

### 4. 音声認識精度評価

```bash
# 1. 音声認識実行（結果をlogsに保存）
python main.py \
  --audio-file "test_data/audio/リアルタイムミーティング翻訳検証音声データ.mp3" \
  --source-lang ja \
  --target-lang en \
  --speaker-name "テストユーザー" \
  --transcription-only

# 2. 精度評価（生成されたログファイルを使用）
python evaluate_transcription.py \
  "test_data/reference/リアルタイムミーティング翻訳検証音声データ_正解データ.txt" \
  "logs/simple_transcription_ja_YYYYMMDD_HHMMSS.txt" \
  --verbose
```

## 📊 期待される評価結果

### 音声認識精度
- **目標精度**: 90%以上
- **評価指標**: WER (Word Error Rate)
- **判定基準**: 
  - 95%以上: ✅ 優秀
  - 90%以上: 🟢 良好
  - 80%以上: 🟡 普通
  - 80%未満: 🔴 要改善

### システム安定性
- **完了率**: 100%（全発話を処理完了）
- **エラー率**: 0%（システムクラッシュなし）
- **終了処理**: 正常終了

## 🔧 対応フォーマット

### 音声ファイル
録音データテスト機能では以下のフォーマットに対応：

- **MP3** ✅ (推奨・テスト済み)
- **WAV** ✅ (高品質)
- **FLAC** ✅ (ロスレス)
- **M4A** ✅ (Apple形式)
- **OGG** ✅ (オープン形式)

### 再生速度
- **1.0**: リアルタイム（実際の時間）
- **2.0**: 2倍速（テスト時間短縮）
- **3.0**: 3倍速（高速テスト）
- **0.5**: 0.5倍速（詳細分析用）

## 📋 注意事項

1. **ファイルパス**: 日本語ファイル名に対応
2. **依存関係**: `librosa`と`soundfile`が必要
3. **メモリ使用量**: 約500MB（通常テスト）
4. **実行時間**: 
   - 1.0倍速: 約70秒
   - 3.0倍速: 約25秒

## 🚀 クイックテスト

```bash
# 環境確認
python check_environment.py --api-test

# 最速テスト（25秒で完了）
python main.py \
  --audio-file "test_data/audio/リアルタイムミーティング翻訳検証音声データ.mp3" \
  --source-lang ja \
  --target-lang en \
  --speaker-name "テストユーザー" \
  --transcription-only \
  --playback-speed 3.0
``` 