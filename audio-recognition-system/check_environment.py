#!/usr/bin/env python3
"""
MVP版環境確認スクリプト
システムの依存関係、設定、動作状況を詳細にチェック

使用方法:
    python check_environment.py
    python check_environment.py --verbose
    python check_environment.py --api-test
"""

import sys
import os
import importlib
import platform
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import argparse

# カラー出力用
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'  # No Color

def print_header(text: str):
    """ヘッダーを出力"""
    print(f"\n{Colors.CYAN}{'='*60}{Colors.NC}")
    print(f"{Colors.CYAN}{text:^60}{Colors.NC}")
    print(f"{Colors.CYAN}{'='*60}{Colors.NC}")

def print_status(item: str, status: bool, details: str = ""):
    """ステータスを色付きで出力"""
    icon = f"{Colors.GREEN}✅{Colors.NC}" if status else f"{Colors.RED}❌{Colors.NC}"
    print(f"{icon} {item}")
    if details:
        print(f"   {Colors.PURPLE}→ {details}{Colors.NC}")

def print_warning(item: str, details: str = ""):
    """警告を出力"""
    print(f"{Colors.YELLOW}⚠️  {item}{Colors.NC}")
    if details:
        print(f"   {Colors.YELLOW}→ {details}{Colors.NC}")

def print_info(text: str):
    """情報を出力"""
    print(f"{Colors.BLUE}ℹ️  {text}{Colors.NC}")

def check_python_version() -> Tuple[bool, str]:
    """Python版を確認"""
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"
    
    if version.major >= 3 and version.minor >= 8:
        return True, version_str
    else:
        return False, f"{version_str} (3.8以上が必要)"

def check_package_installation() -> Dict[str, Tuple[bool, str]]:
    """パッケージのインストール状況を確認"""
    packages = {
        # API関連
        'anthropic': 'Claude API',
        'google.auth': 'Google認証',
        'googleapiclient': 'Google API クライアント',
        'dotenv': '環境変数管理',
        
        # 音声処理
        'pyaudio': 'PyAudio',
        'sounddevice': 'SoundDevice',
        'noisereduce': 'ノイズ除去',
        
        # 機械学習
        'torch': 'PyTorch',
        'transformers': 'Transformers',
        'accelerate': 'Accelerate',
        
        # 音声認識
        'mlx_whisper': 'MLX Whisper (macOS最適化)',
        'whisper': 'OpenAI Whisper',
        
        # データ処理
        'numpy': 'NumPy',
        'scipy': 'SciPy',
    }
    
    results = {}
    for package, description in packages.items():
        try:
            importlib.import_module(package)
            # バージョン情報を取得
            try:
                mod = importlib.import_module(package)
                version = getattr(mod, '__version__', 'バージョン不明')
                results[description] = (True, f"v{version}")
            except:
                results[description] = (True, "インストール済み")
        except ImportError:
            results[description] = (False, "未インストール")
    
    return results

def check_system_info() -> Dict[str, str]:
    """システム情報を取得"""
    return {
        'OS': platform.system(),
        'OS版': platform.release(),
        'アーキテクチャ': platform.machine(),
        'Python実行パス': sys.executable,
        'Python版': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }

def check_audio_devices() -> Tuple[bool, List[str]]:
    """音声デバイスの確認"""
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devices = []
        
        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                input_devices.append(f"Device {i}: {device['name']} ({device['max_input_channels']}ch)")
        
        return len(input_devices) > 0, input_devices
    except Exception as e:
        return False, [f"エラー: {str(e)}"]

def check_files_and_directories() -> Dict[str, bool]:
    """重要なファイル・ディレクトリの存在確認"""
    items = {
        'main_mvp.py': Path('main_mvp.py').exists(),
        'config/mvp_config.py': Path('config/mvp_config.py').exists(),
        'translation/translator.py': Path('translation/translator.py').exists(),
        'output/basic_google_docs_writer.py': Path('output/basic_google_docs_writer.py').exists(),
        'recognition/speech_recognition.py': Path('recognition/speech_recognition.py').exists(),
        '.env.example': Path('.env.example').exists(),
        '.env': Path('.env').exists(),
        'credentials.json': Path('credentials.json').exists(),
        'SETUP_GUIDE.md': Path('SETUP_GUIDE.md').exists(),
    }
    return items

def check_mvp_modules() -> Tuple[bool, str]:
    """MVP版モジュールのインポート確認"""
    try:
        # パス追加
        sys.path.append(os.path.join(os.path.dirname(__file__), 'translation'))
        
        from translator import ClaudeTranslator
        print("✅ ClaudeTranslator import成功")
        return True, "全てのMVPモジュールが正常にインポートできます"
    except ImportError as e:
        print(f"❌ ClaudeTranslator import失敗: {e}")
        return False, f"インポートエラー: {str(e)}"
    except Exception as e:
        print(f"❌ ClaudeTranslator テストエラー: {e}")
        return False, f"テストエラー: {str(e)}"

def check_api_configuration() -> Dict[str, Tuple[bool, str]]:
    """API設定の確認"""
    results = {}
    
    # .envファイルの確認
    env_path = Path('.env')
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv()
            
            # Claude API設定
            claude_key = os.getenv('CLAUDE_API_KEY')
            if claude_key and claude_key != 'your_claude_api_key_here':
                results['Claude APIキー'] = (True, "設定済み")
            else:
                results['Claude APIキー'] = (False, "未設定または例文のまま")
            
            # Google Docs設定
            creds_path = os.getenv('GOOGLE_DOCS_CREDENTIALS_PATH', 'credentials.json')
            if Path(creds_path).exists():
                results['Google Docs認証ファイル'] = (True, f"存在: {creds_path}")
            else:
                results['Google Docs認証ファイル'] = (False, f"未存在: {creds_path}")
                
        except Exception as e:
            results['環境変数読み込み'] = (False, f"エラー: {str(e)}")
    else:
        results['.env ファイル'] = (False, "存在しません")
    
    return results

def test_apis(verbose: bool = False) -> Dict[str, Tuple[bool, str]]:
    """API接続テスト（オプション）"""
    results = {}
    
    if verbose:
        print_info("API接続テストを実行中...")
    
    # Claude APIテスト
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), 'translation'))
        from translator import ClaudeTranslator
        from dotenv import load_dotenv
        
        load_dotenv()
        api_key = os.getenv('CLAUDE_API_KEY')
        
        if api_key and api_key != 'your_claude_api_key_here':
            translator = ClaudeTranslator(api_key, 'claude-3-7-sonnet-20250219')
            if translator.test_connection():
                results['Claude API接続'] = (True, "接続成功")
            else:
                results['Claude API接続'] = (False, "接続失敗")
        else:
            results['Claude API接続'] = (False, "APIキー未設定")
    except Exception as e:
        results['Claude API接続'] = (False, f"テストエラー: {str(e)}")
    
    # Google Docs APIテスト
    try:
        sys.path.append(os.path.join(os.path.dirname(__file__), 'output'))
        from basic_google_docs_writer import BasicGoogleDocsWriter
        
        creds_path = os.getenv('GOOGLE_DOCS_CREDENTIALS_PATH', 'credentials.json')
        token_path = os.getenv('GOOGLE_DOCS_TOKEN_PATH', 'token.json')
        
        if Path(creds_path).exists():
            writer = BasicGoogleDocsWriter(creds_path, token_path)
            if writer.test_connection():
                results['Google Docs API接続'] = (True, "接続成功")
            else:
                results['Google Docs API接続'] = (False, "接続失敗")
        else:
            results['Google Docs API接続'] = (False, "認証ファイル未存在")
    except Exception as e:
        results['Google Docs API接続'] = (False, f"テストエラー: {str(e)}")
    
    return results

def main():
    parser = argparse.ArgumentParser(description='MVP版環境確認スクリプト')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細出力')
    parser.add_argument('--api-test', '-a', action='store_true', help='API接続テストを実行')
    args = parser.parse_args()

    print_header("MVP版環境確認スクリプト")
    
    # 1. システム情報
    print_header("システム情報")
    system_info = check_system_info()
    for key, value in system_info.items():
        print(f"{Colors.BLUE}{key:<15}: {Colors.NC}{value}")
    
    # 2. Python版確認
    print_header("Python環境")
    python_ok, python_version = check_python_version()
    print_status(f"Python版: {python_version}", python_ok, 
                "Python 3.8以上が推奨" if python_ok else "Python 3.8以上にアップグレードしてください")
    
    # 3. パッケージ確認
    print_header("依存関係パッケージ")
    packages = check_package_installation()
    for package, (status, details) in packages.items():
        print_status(package, status, details)
    
    # 4. 音声デバイス確認
    print_header("音声デバイス")
    audio_ok, devices = check_audio_devices()
    if audio_ok:
        print_status("音声入力デバイス", True, f"{len(devices)}個のデバイスを検出")
        if args.verbose:
            for device in devices:
                print(f"   {Colors.CYAN}• {device}{Colors.NC}")
    else:
        print_status("音声入力デバイス", False, "デバイスが検出されませんでした")
    
    # 5. ファイル・ディレクトリ確認
    print_header("ファイル・ディレクトリ")
    files = check_files_and_directories()
    for item, exists in files.items():
        print_status(item, exists, "存在" if exists else "未存在")
    
    # 6. MVPモジュール確認
    print_header("システムモジュール")
    mvp_ok, mvp_details = check_mvp_modules()
    print_status("MVP版モジュール", mvp_ok, mvp_details)
    
    # 7. API設定確認
    print_header("API設定")
    api_configs = check_api_configuration()
    for item, (status, details) in api_configs.items():
        print_status(item, status, details)
    
    # 8. API接続テスト（オプション）
    if args.api_test:
        print_header("API接続テスト")
        api_tests = test_apis(args.verbose)
        for test, (status, details) in api_tests.items():
            print_status(test, status, details)
    
    # 9. 総合判定
    print_header("総合判定")
    
    # 必須項目の確認
    required_checks = [
        python_ok,
        packages.get('Claude API', (False, ""))[0],
        packages.get('Google API クライアント', (False, ""))[0],
        packages.get('PyAudio', (False, ""))[0],
        packages.get('PyTorch', (False, ""))[0],
        mvp_ok,
        files.get('main_mvp.py', False),
    ]
    
    all_required_ok = all(required_checks)
    
    if all_required_ok:
        print_status("システム準備状況", True, "MVP版実行準備完了")
        print_info("次のステップ: APIキー設定後にシステムテストを実行してください")
    else:
        print_status("システム準備状況", False, "必須要件が不足しています")
        print_warning("setup_mvp.shを実行してセットアップを完了してください")
    
    # 推奨項目の確認
    optional_items = [
        packages.get('MLX Whisper (macOS最適化)', (False, ""))[0],
        files.get('.env', False),
        files.get('credentials.json', False),
    ]
    
    if any(optional_items):
        print_info("推奨機能が一部利用可能です")
    
    print(f"\n{Colors.CYAN}詳細なセットアップ手順については SETUP_GUIDE.md を参照してください{Colors.NC}")

if __name__ == "__main__":
    main() 