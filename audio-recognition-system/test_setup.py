#!/usr/bin/env python3
"""
MVP版環境構築検証スクリプト
セットアップが正しく完了したかを詳細にテスト

使用方法:
    python test_setup.py
    python test_setup.py --full  # API接続テストも含む
    python test_setup.py --quick # 基本テストのみ
"""

import sys
import os
import time
import tempfile
import traceback
from pathlib import Path
from typing import List, Tuple, Dict
import argparse

# カラー出力
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    PURPLE = '\033[0;35m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'

class TestResult:
    def __init__(self, name: str, success: bool, message: str = "", details: str = ""):
        self.name = name
        self.success = success
        self.message = message
        self.details = details
        self.duration = 0.0

class MVPSetupTester:
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: List[TestResult] = []
        self.start_time = time.time()

    def log(self, message: str, color: str = Colors.NC):
        print(f"{color}{message}{Colors.NC}")

    def log_test_start(self, test_name: str):
        if self.verbose:
            self.log(f"📋 テスト開始: {test_name}", Colors.BLUE)

    def log_test_result(self, result: TestResult):
        icon = f"{Colors.GREEN}✅" if result.success else f"{Colors.RED}❌"
        duration_str = f" ({result.duration:.2f}s)" if result.duration > 0.1 else ""
        self.log(f"{icon} {result.name}{duration_str}{Colors.NC}")
        
        if result.message:
            self.log(f"   {Colors.PURPLE}→ {result.message}{Colors.NC}")
        
        if not result.success and result.details and self.verbose:
            self.log(f"   {Colors.RED}詳細: {result.details}{Colors.NC}")

    def run_test(self, test_func, test_name: str) -> TestResult:
        """テストを実行して結果を記録"""
        self.log_test_start(test_name)
        start_time = time.time()
        
        try:
            success, message, details = test_func()
            result = TestResult(test_name, success, message, details)
        except Exception as e:
            result = TestResult(test_name, False, f"例外発生: {str(e)}", traceback.format_exc())
        
        result.duration = time.time() - start_time
        self.results.append(result)
        self.log_test_result(result)
        return result

    def test_python_version(self) -> Tuple[bool, str, str]:
        """Python版テスト"""
        version = sys.version_info
        if version.major >= 3 and version.minor >= 8:
            return True, f"Python {version.major}.{version.minor}.{version.micro}", ""
        else:
            return False, f"Python {version.major}.{version.minor}.{version.micro} (3.8以上が必要)", ""

    def test_package_imports(self) -> Tuple[bool, str, str]:
        """重要パッケージのインポートテスト"""
        critical_packages = [
            ('anthropic', 'Claude API'),
            ('google.auth', 'Google認証'),
            ('googleapiclient', 'Google API'),
            ('pyaudio', 'PyAudio'),
            ('torch', 'PyTorch'),
            ('transformers', 'Transformers'),
        ]
        
        failed_packages = []
        for package, description in critical_packages:
            try:
                __import__(package)
            except ImportError as e:
                failed_packages.append(f"{description} ({package})")
        
        if failed_packages:
            return False, f"{len(failed_packages)}個のパッケージが未インストール", ", ".join(failed_packages)
        else:
            return True, f"{len(critical_packages)}個の重要パッケージが利用可能", ""

    def test_optional_packages(self) -> Tuple[bool, str, str]:
        """オプションパッケージのテスト"""
        optional_packages = [
            ('mlx_whisper', 'MLX Whisper (macOS最適化)'),
            ('whisper', 'OpenAI Whisper'),
            ('noisereduce', 'ノイズ除去'),
        ]
        
        available_packages = []
        for package, description in optional_packages:
            try:
                __import__(package)
                available_packages.append(description)
            except ImportError:
                pass
        
        return True, f"{len(available_packages)}個のオプションパッケージが利用可能", ", ".join(available_packages)

    def test_mvp_modules(self) -> Tuple[bool, str, str]:
        """MVP版モジュールのインポートテスト"""
        # パス追加
        sys.path.append(os.path.join(os.path.dirname(__file__), 'config'))
        sys.path.append(os.path.join(os.path.dirname(__file__), 'translation'))
        sys.path.append(os.path.join(os.path.dirname(__file__), 'output'))
        
        mvp_modules = [
            ('mvp_config', 'MVP設定管理'),
            ('claude_translator', 'Claude翻訳'),
            ('basic_google_docs_writer', 'Google Docs出力'),
        ]
        
        failed_modules = []
        for module, description in mvp_modules:
            try:
                __import__(module)
            except ImportError as e:
                failed_modules.append(f"{description} ({module})")
        
        if failed_modules:
            return False, f"{len(failed_modules)}個のMVPモジュールが利用不可", ", ".join(failed_modules)
        else:
            return True, "全てのMVPモジュールが正常にインポート可能", ""

    def test_audio_devices(self) -> Tuple[bool, str, str]:
        """音声デバイステスト"""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            input_devices = [d for d in devices if d['max_input_channels'] > 0]
            
            if input_devices:
                device_names = [d['name'] for d in input_devices[:3]]  # 最初の3つ
                return True, f"{len(input_devices)}個の入力デバイスを検出", ", ".join(device_names)
            else:
                return False, "音声入力デバイスが見つかりません", "マイクの接続を確認してください"
        except Exception as e:
            return False, "音声デバイス確認でエラー", str(e)

    def test_file_structure(self) -> Tuple[bool, str, str]:
        """ファイル構造テスト"""
        required_files = [
            'main_mvp.py',
            'config/mvp_config.py',
            'translation/claude_translator.py',
            'output/basic_google_docs_writer.py',
            '.env.example',
        ]
        
        missing_files = []
        for file_path in required_files:
            if not Path(file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            return False, f"{len(missing_files)}個の必須ファイルが不足", ", ".join(missing_files)
        else:
            return True, f"{len(required_files)}個の必須ファイルが存在", ""

    def test_env_configuration(self) -> Tuple[bool, str, str]:
        """.env設定テスト"""
        env_path = Path('.env')
        if not env_path.exists():
            return False, ".envファイルが存在しません", "cp .env.example .env を実行してください"
        
        try:
            from dotenv import load_dotenv
            load_dotenv()
            
            claude_key = os.getenv('CLAUDE_API_KEY')
            if not claude_key:
                return False, "CLAUDE_API_KEYが設定されていません", ""
            elif claude_key == 'your_claude_api_key_here':
                return False, "CLAUDE_API_KEYが例文のままです", "実際のAPIキーを設定してください"
            else:
                return True, "CLAUDE_API_KEYが設定済み", ""
        except Exception as e:
            return False, ".env読み込みエラー", str(e)

    def test_system_help(self) -> Tuple[bool, str, str]:
        """システムヘルプ表示テスト"""
        try:
            import subprocess
            result = subprocess.run(
                [sys.executable, 'main_mvp.py', '--help'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return True, "システムが正常に起動可能", ""
            else:
                return False, f"システム起動失敗 (exit code: {result.returncode})", result.stderr
        except subprocess.TimeoutExpired:
            return False, "システム起動がタイムアウト", "30秒以内に応答がありませんでした"
        except Exception as e:
            return False, "システム起動テストでエラー", str(e)

    def test_api_connections(self) -> Tuple[bool, str, str]:
        """API接続テスト（オプション）"""
        sys.path.append(os.path.join(os.path.dirname(__file__), 'translation'))
        
        try:
            from claude_translator import ClaudeTranslator
            from dotenv import load_dotenv
            
            load_dotenv()
            api_key = os.getenv('CLAUDE_API_KEY')
            
            if not api_key or api_key == 'your_claude_api_key_here':
                return False, "Claude APIキーが未設定", "実際のAPIキーを設定してください"
            
            translator = ClaudeTranslator(api_key, 'claude-3-7-sonnet-20250219')
            if translator.test_connection():
                return True, "Claude API接続成功", ""
            else:
                return False, "Claude API接続失敗", "APIキーまたはネットワーク接続を確認してください"
        except Exception as e:
            return False, "Claude APIテストでエラー", str(e)

    def test_memory_usage(self) -> Tuple[bool, str, str]:
        """メモリ使用量テスト"""
        try:
            import psutil
            memory = psutil.virtual_memory()
            available_gb = memory.available / (1024**3)
            
            if available_gb < 2.0:
                return False, f"利用可能メモリ不足: {available_gb:.1f}GB", "2GB以上のメモリが推奨されます"
            elif available_gb < 4.0:
                return True, f"利用可能メモリ: {available_gb:.1f}GB (最小要件を満たす)", ""
            else:
                return True, f"利用可能メモリ: {available_gb:.1f}GB (十分)", ""
        except Exception as e:
            return True, "メモリ確認スキップ", str(e)

    def run_all_tests(self, test_apis: bool = False) -> Dict[str, int]:
        """全テストを実行"""
        self.log(f"\n{Colors.CYAN}{'='*60}{Colors.NC}")
        self.log(f"{Colors.CYAN}MVP版セットアップ検証テスト開始{Colors.NC}")
        self.log(f"{Colors.CYAN}{'='*60}{Colors.NC}")

        # 基本テスト
        basic_tests = [
            (self.test_python_version, "Python版確認"),
            (self.test_package_imports, "重要パッケージインポート"),
            (self.test_optional_packages, "オプションパッケージ確認"),
            (self.test_mvp_modules, "MVPモジュールインポート"),
            (self.test_file_structure, "ファイル構造確認"),
            (self.test_env_configuration, "環境変数設定確認"),
            (self.test_audio_devices, "音声デバイス確認"),
            (self.test_memory_usage, "メモリ使用量確認"),
            (self.test_system_help, "システム起動確認"),
        ]

        for test_func, test_name in basic_tests:
            self.run_test(test_func, test_name)

        # API接続テスト（オプション）
        if test_apis:
            self.log(f"\n{Colors.BLUE}API接続テスト実行中...{Colors.NC}")
            self.run_test(self.test_api_connections, "Claude API接続確認")

        # 結果サマリー
        self.print_summary()
        
        # 統計情報を返す
        success_count = sum(1 for r in self.results if r.success)
        total_count = len(self.results)
        failed_count = total_count - success_count
        
        return {
            'total': total_count,
            'success': success_count,
            'failed': failed_count
        }

    def print_summary(self):
        """テスト結果のサマリーを出力"""
        total_time = time.time() - self.start_time
        success_count = sum(1 for r in self.results if r.success)
        total_count = len(self.results)
        failed_count = total_count - success_count

        self.log(f"\n{Colors.CYAN}{'='*60}{Colors.NC}")
        self.log(f"{Colors.CYAN}テスト結果サマリー{Colors.NC}")
        self.log(f"{Colors.CYAN}{'='*60}{Colors.NC}")

        self.log(f"実行時間: {total_time:.2f}秒")
        self.log(f"総テスト数: {total_count}")
        self.log(f"{Colors.GREEN}成功: {success_count}{Colors.NC}")
        
        if failed_count > 0:
            self.log(f"{Colors.RED}失敗: {failed_count}{Colors.NC}")
            self.log(f"\n{Colors.RED}失敗したテスト:{Colors.NC}")
            for result in self.results:
                if not result.success:
                    self.log(f"{Colors.RED}  ❌ {result.name}: {result.message}{Colors.NC}")

        # 総合判定
        if failed_count == 0:
            self.log(f"\n{Colors.GREEN}🎉 全テスト合格！MVP版の準備が完了しています{Colors.NC}")
            self.log(f"{Colors.BLUE}次のステップ: APIキー設定後にシステムテストを実行してください{Colors.NC}")
        elif failed_count <= 2:
            self.log(f"\n{Colors.YELLOW}⚠️  大部分のテストに合格しました（軽微な問題あり）{Colors.NC}")
            self.log(f"{Colors.BLUE}問題を修正後、システムテストを実行してください{Colors.NC}")
        else:
            self.log(f"\n{Colors.RED}❌ 重要な問題が検出されました{Colors.NC}")
            self.log(f"{Colors.YELLOW}setup_mvp.shを再実行するか、SETUP_GUIDE.mdを参照してください{Colors.NC}")

def main():
    parser = argparse.ArgumentParser(description='MVP版環境構築検証スクリプト')
    parser.add_argument('--full', action='store_true', help='API接続テストも実行')
    parser.add_argument('--quick', action='store_true', help='基本テストのみ（高速）')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細出力')
    args = parser.parse_args()

    tester = MVPSetupTester(verbose=args.verbose)
    
    # APIテストの実行判定
    test_apis = args.full and not args.quick
    
    stats = tester.run_all_tests(test_apis=test_apis)
    
    # 終了コード設定
    exit_code = 0 if stats['failed'] == 0 else 1
    sys.exit(exit_code)

if __name__ == "__main__":
    main() 