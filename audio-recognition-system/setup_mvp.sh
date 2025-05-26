#!/bin/bash

# MVP版音声認識・翻訳・Google Docs出力システム 自動セットアップスクリプト
# 使用方法: chmod +x setup_mvp.sh && ./setup_mvp.sh

set -e  # エラー時に停止

# カラー出力用
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ログ関数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# スクリプト開始
echo "================================================================"
echo "MVP版音声認識・翻訳・Google Docs出力システム"
echo "自動セットアップスクリプト"
echo "================================================================"
echo

# 前提条件確認
log_info "前提条件確認中..."

# Python3のチェック
if ! command -v python3 &> /dev/null; then
    log_error "Python3がインストールされていません"
    echo "Python 3.8以上をインストールしてからもう一度実行してください"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
log_info "Python バージョン: $PYTHON_VERSION"

# macOSの確認
if [[ "$OSTYPE" == "darwin"* ]]; then
    log_success "macOS環境を検出（Apple Silicon最適化利用可能）"
    MACOS_OPTIMIZED=true
else
    log_warning "非macOS環境（MLX最適化は利用できません）"
    MACOS_OPTIMIZED=false
fi

# 1. 仮想環境の作成
log_info "仮想環境（venv_mvp）を作成中..."
if [ -d "venv_mvp" ]; then
    log_warning "既存の仮想環境を発見。削除して再作成しますか？ (y/N)"
    read -r response
    if [[ "$response" =~ ^[Yy]$ ]]; then
        rm -rf venv_mvp
        log_info "既存の仮想環境を削除しました"
    else
        log_info "既存の仮想環境を使用します"
    fi
fi

if [ ! -d "venv_mvp" ]; then
    python3 -m venv venv_mvp
    log_success "仮想環境を作成しました"
fi

# 2. 仮想環境の有効化
log_info "仮想環境を有効化中..."
source venv_mvp/bin/activate

# 3. pipのアップグレード
log_info "pipをアップグレード中..."
python -m pip install --upgrade pip

# 4. 依存関係のインストール
log_info "依存関係をインストール中..."

# Phase 1: 基本API関連パッケージ
log_info "Phase 1: API関連パッケージをインストール中..."
pip install anthropic google-api-python-client google-auth-httplib2 google-auth-oauthlib google-auth python-dotenv

# Phase 2: 音声処理パッケージ
log_info "Phase 2: 音声処理パッケージをインストール中..."
pip install pyaudio sounddevice noisereduce

# Phase 3: 機械学習パッケージ
log_info "Phase 3: 機械学習パッケージをインストール中..."
pip install torch transformers accelerate

# Phase 4: macOS最適化パッケージ（条件付き）
if [ "$MACOS_OPTIMIZED" = true ]; then
    log_info "Phase 4: macOS最適化パッケージをインストール中..."
    pip install mlx-lm mlx-whisper
    log_success "macOS最適化パッケージをインストールしました（3-10倍高速化）"
else
    log_warning "macOS最適化パッケージはスキップしました"
fi

# Phase 5: OpenAI Whisper（オプション・エラー時はスキップ）
log_info "Phase 5: OpenAI Whisperをインストール中（エラー時はスキップ）..."
if pip install openai-whisper >/dev/null 2>&1; then
    log_success "OpenAI Whisperをインストールしました"
else
    log_warning "OpenAI Whisperのインストールに失敗しましたが、MLX Whisperで代替可能です"
    log_info "音声認識にはMLX Whisper（3-10倍高速）を使用します"
fi

# 5. Pythonパッケージ構造の修正
log_info "Pythonパッケージ構造を修正中..."
# 必要に応じて__init__.pyファイルを作成/削除
touch translation/__init__.py
touch output/__init__.py
# configディレクトリの__init__.pyは削除（名前衝突回避のため）
rm -f config/__init__.py

# 6. 環境変数ファイルの作成
log_info "環境設定ファイルを確認中..."
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        log_success ".env.exampleから.envファイルを作成しました"
        log_warning "APIキーの設定が必要です（Claude API、Google Docs API）"
        echo
        echo "🔑 APIキーの設定方法:"
        echo "1. Claude APIキー取得: https://console.anthropic.com/"
        echo "2. Google Docs API設定: https://console.cloud.google.com/"
        echo "3. .envファイルを編集してAPIキーを設定"
        echo "   nano .env"
        echo
    else
        log_warning ".env.exampleファイルが見つかりません"
    fi
else
    log_info ".envファイルは既に存在します"
fi

# 7. 動作確認テスト
log_info "基本動作確認テストを実行中..."

# インポートテスト
log_info "パッケージインポートテストを実行中..."
python -c "
try:
    import anthropic
    import google.auth
    print('✅ API関連パッケージ: 正常')
except ImportError as e:
    print('❌ API関連パッケージ: エラー -', e)
    exit(1)

try:
    import pyaudio
    import sounddevice
    print('✅ 音声処理パッケージ: 正常')
except ImportError as e:
    print('❌ 音声処理パッケージ: エラー -', e)
    exit(1)

try:
    import torch
    import transformers
    print('✅ 機械学習パッケージ: 正常')
except ImportError as e:
    print('❌ 機械学習パッケージ: エラー -', e)
    exit(1)

try:
    if '$MACOS_OPTIMIZED' == 'true':
        import mlx_whisper
        print('✅ macOS最適化パッケージ: 正常')
except ImportError as e:
    print('⚠️ macOS最適化パッケージ: 警告 -', e)
"

# システムモジュールのインポートテスト
log_info "システムモジュールインポートテストを実行中..."
python -c "
import sys
import os
current_dir = os.getcwd()
sys.path.append(os.path.join(current_dir, 'config'))
sys.path.append(os.path.join(current_dir, 'translation'))
sys.path.append(os.path.join(current_dir, 'output'))

try:
    from mvp_config import MVPConfig
    from claude_translator import ClaudeTranslator
    from basic_google_docs_writer import BasicGoogleDocsWriter
    print('✅ MVP版システムモジュール: 正常')
except ImportError as e:
    print('❌ MVP版システムモジュール: エラー -', e)
    exit(1)
"

# ヘルプ表示テスト
log_info "システム起動テストを実行中..."
if python main_mvp.py --help > /dev/null 2>&1; then
    log_success "システム起動テスト: 成功"
else
    log_error "システム起動テスト: 失敗"
    exit 1
fi

# 8. セットアップ完了
echo
echo "================================================================"
log_success "MVP版セットアップが完了しました！"
echo "================================================================"
echo

echo "📋 次のステップ:"
echo "1. Claude APIキーを取得して.envファイルに設定"
echo "   - https://console.anthropic.com/"
echo "   - CLAUDE_API_KEY=your_api_key_here"
echo
echo "2. Google Docs API認証を設定"
echo "   - https://console.cloud.google.com/"
echo "   - credentials.jsonをダウンロードしてプロジェクトルートに配置"
echo
echo "3. システムテスト実行"
echo "   python main_mvp.py --source-lang ja --target-lang en --speaker-name 'テストユーザー'"
echo
echo "📁 作成されたファイル:"
echo "   - venv_mvp/ (仮想環境)"
echo "   - .env (環境変数ファイル)"
echo "   - translation/__init__.py"
echo "   - output/__init__.py"
echo
echo "📖 詳細情報:"
echo "   - セットアップガイド: SETUP_GUIDE.md"
echo "   - ステータス確認: MVP_TEST_STATUS.md"
echo
echo "🚀 仮想環境の有効化コマンド:"
echo "   source venv_mvp/bin/activate"

# 仮想環境をアクティブのまま終了
log_info "仮想環境はアクティブのままです" 