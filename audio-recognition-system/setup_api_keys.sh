#!/bin/bash

# APIキー設定支援スクリプト
# 使用方法: chmod +x setup_api_keys.sh && ./setup_api_keys.sh

set -e

# カラー出力用
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

echo "================================================================"
echo "MVP版 APIキー設定支援スクリプト"
echo "================================================================"
echo

# .envファイルの確認
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        log_info ".env.exampleから.envファイルを作成します..."
        cp .env.example .env
        log_success ".envファイルを作成しました"
    else
        log_error ".env.exampleファイルが見つかりません"
        exit 1
    fi
fi

# Claude APIキーの設定
echo
log_info "🤖 Claude APIキーの設定"
echo "1. https://console.anthropic.com/ にアクセス"
echo "2. アカウントを作成またはログイン"
echo "3. 'Create Key'をクリックしてAPIキーを生成"
echo "4. APIキーをコピー"
echo

read -p "Claude APIキーを貼り付けてください（Enterで設定をスキップ）: " claude_api_key

if [ ! -z "$claude_api_key" ]; then
    # .envファイルでClaude APIキーを更新
    if grep -q "CLAUDE_API_KEY=" .env; then
        sed -i '' "s/CLAUDE_API_KEY=.*/CLAUDE_API_KEY=$claude_api_key/" .env
    else
        echo "CLAUDE_API_KEY=$claude_api_key" >> .env
    fi
    log_success "Claude APIキーを設定しました"
else
    log_warning "Claude APIキーの設定をスキップしました"
fi

# Google Docs API設定
echo
log_info "📄 Google Docs API設定"
echo "1. https://console.cloud.google.com/ にアクセス"
echo "2. 新しいプロジェクトを作成または既存を選択"
echo "3. 'APIs & Services' → 'Library' から 'Google Docs API' を有効化"
echo "4. 'APIs & Services' → 'Credentials' に移動"
echo "5. '+ CREATE CREDENTIALS' → 'OAuth 2.0 Client IDs'"
echo "6. Application type: 'Desktop application'"
echo "7. credentials.jsonをダウンロード"
echo "8. ファイルをプロジェクトルートに配置"
echo

if [ -f "credentials.json" ]; then
    log_success "credentials.jsonが見つかりました"
else
    log_warning "credentials.jsonが見つかりません"
    echo "Google Docs APIを使用するには credentials.json が必要です"
    echo "上記の手順に従ってダウンロードし、プロジェクトルートに配置してください"
fi

# 設定確認
echo
log_info "📋 設定確認"

# Claude APIキー確認
claude_key=$(grep "CLAUDE_API_KEY=" .env | cut -d'=' -f2)
if [ ! -z "$claude_key" ] && [ "$claude_key" != "your_claude_api_key_here" ]; then
    log_success "✅ Claude APIキー: 設定済み"
else
    log_warning "❌ Claude APIキー: 未設定"
fi

# Google Docs認証ファイル確認
if [ -f "credentials.json" ]; then
    log_success "✅ Google Docs認証ファイル: 存在"
else
    log_warning "❌ Google Docs認証ファイル: 未存在"
fi

echo
echo "================================================================"
log_info "次のステップ:"
echo "1. 環境確認: python check_environment.py"
echo "2. セットアップ検証: python test_setup.py"
echo "3. システムテスト: python main_mvp.py --source-lang ja --target-lang en --speaker-name 'テストユーザー'"
echo "================================================================" 