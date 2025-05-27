"""
MVP版設定管理モジュール
シンプルな設定クラスと環境変数管理

MVP戦略: 複雑な設定は後回し、固定値と基本的な環境変数のみ
"""

from dataclasses import dataclass
from typing import Optional
import os
import logging
from dotenv import load_dotenv

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# .envファイルを読み込み
load_dotenv()


@dataclass
class MVPConfig:
    """MVP版設定クラス（シンプル構成）"""
    
    # 言語設定（必須）
    source_lang: str
    target_lang: str
    speaker_name: str
    
    # デバイス設定
    input_device: Optional[int] = 0  # デフォルト: Device 0（通常ヘッドセット）
    sample_rate: int = 16000
    chunk_size: int = 10  # 固定10秒（MVP版）
    
    # 音声認識モデル設定
    speech_model: str = "large-v3"  # デフォルト: 最高精度
    
    # Claude API設定
    claude_api_key: Optional[str] = None
    claude_model_name: str = "claude-3-7-sonnet-20250219"  # MVP版固定
    
    # Google Docs設定
    google_docs_id: Optional[str] = None
    google_credentials_path: str = "credentials.json"
    google_token_path: str = "token.json"
    
    # 出力設定
    output_dir: Optional[str] = None
    log_level: str = "INFO"
    
    # 機能無効化フラグ
    disable_translation: bool = False
    disable_docs_output: bool = False
    transcription_only: bool = False
    
    # ログ制御フラグ
    verbose: bool = False
    
    def __post_init__(self):
        """初期化後の処理"""
        # 環境変数から設定を読み込み
        self._load_from_env()
        
    def _load_from_env(self):
        """環境変数から設定を読み込み"""
        # Claude API設定
        if not self.claude_api_key:
            self.claude_api_key = os.getenv("CLAUDE_API_KEY")
        
        # Claude モデル名（環境変数で上書き可能）
        env_model = os.getenv("CLAUDE_MODEL_NAME")
        if env_model:
            self.claude_model_name = env_model
        
        # Google Docs設定
        env_docs_id = os.getenv("GOOGLE_DOCS_ID")
        if env_docs_id:
            self.google_docs_id = env_docs_id
            
        env_credentials = os.getenv("GOOGLE_DOCS_CREDENTIALS_PATH")
        if env_credentials:
            self.google_credentials_path = env_credentials
            
        env_token = os.getenv("GOOGLE_DOCS_TOKEN_PATH")
        if env_token:
            self.google_token_path = env_token
        
        # 音声設定（環境変数で上書き可能）
        env_input_device = os.getenv("AUDIO_INPUT_DEVICE")
        if env_input_device:
            try:
                self.input_device = int(env_input_device)
            except ValueError:
                logger.warning(f"不正なAUDIO_INPUT_DEVICE値: {env_input_device}")
        
        env_chunk_size = os.getenv("AUDIO_CHUNK_SIZE")
        if env_chunk_size:
            try:
                self.chunk_size = int(env_chunk_size)
            except ValueError:
                logger.warning(f"不正なAUDIO_CHUNK_SIZE値: {env_chunk_size}")
        
        env_sample_rate = os.getenv("AUDIO_SAMPLE_RATE")
        if env_sample_rate:
            try:
                self.sample_rate = int(env_sample_rate)
            except ValueError:
                logger.warning(f"不正なAUDIO_SAMPLE_RATE値: {env_sample_rate}")
        
        # ログレベル
        env_log_level = os.getenv("LOG_LEVEL")
        if env_log_level:
            self.log_level = env_log_level
    
    def validate(self) -> tuple[bool, list[str]]:
        """
        設定の妥当性をチェック
        
        Returns:
            tuple[bool, list[str]]: (成功フラグ, エラーメッセージリスト)
        """
        errors = []
        
        # 必須設定のチェック
        if not self.source_lang:
            errors.append("発話言語（source_lang）が指定されていません")
        
        if not self.target_lang:
            errors.append("翻訳先言語（target_lang）が指定されていません")
        
        if not self.speaker_name:
            errors.append("発話者名（speaker_name）が指定されていません")
        
        if not self.disable_translation and not self.claude_api_key:
            errors.append("Claude APIキー（CLAUDE_API_KEY）が設定されていません")
        
        # 言語設定のチェック
        supported_langs = ['ja', 'en', 'ko', 'zh', 'es', 'fr', 'de']
        if self.source_lang not in supported_langs:
            errors.append(f"サポートされていない発話言語: {self.source_lang}")
        
        if self.target_lang not in supported_langs:
            errors.append(f"サポートされていない翻訳先言語: {self.target_lang}")
        
        if not self.disable_translation and self.source_lang == self.target_lang:
            errors.append("発話言語と翻訳先言語が同じです")
        
        # 音声設定のチェック
        if self.chunk_size < 5 or self.chunk_size > 30:
            errors.append(f"チャンクサイズは5-30秒の範囲で指定してください: {self.chunk_size}")
        
        if self.sample_rate not in [16000, 44100, 48000]:
            errors.append(f"サポートされていないサンプルレート: {self.sample_rate}")
        
        # 音声デバイス設定のチェック
        if self.input_device is not None and self.input_device < 0:
            errors.append(f"入力デバイスIDは0以上である必要があります: {self.input_device}")
        
        # Google Docs設定のチェック（IDが指定されている場合）
        if self.google_docs_id:
            if not os.path.exists(self.google_credentials_path):
                errors.append(f"Google Docs認証ファイルが見つかりません: {self.google_credentials_path}")
        
        return len(errors) == 0, errors
    
    def print_config(self):
        """設定内容を表示"""
        print("\n=== MVP設定情報 ===")
        print(f"発話言語: {self.source_lang}")
        print(f"翻訳先言語: {self.target_lang}")
        print(f"発話者名: {self.speaker_name}")
        print(f"入力デバイス: {self.input_device if self.input_device is not None else 'デフォルト'} (0=ヘッドセット推奨)")
        print(f"サンプリングレート: {self.sample_rate} Hz")
        print(f"チャンクサイズ: {self.chunk_size} 秒")
        print(f"音声認識モデル: {self.speech_model}")
        
        # 機能有効/無効状態を表示
        if self.transcription_only:
            print("動作モード: 音声認識専用（翻訳・出力無効）")
        else:
            print(f"翻訳機能: {'無効' if self.disable_translation else '有効'}")
            if not self.disable_translation:
                print(f"Claudeモデル: {self.claude_model_name}")
            print(f"Google Docs出力: {'無効' if self.disable_docs_output else '有効'}")
            if not self.disable_docs_output:
                print(f"Google DocsID: {self.google_docs_id if self.google_docs_id else '未指定'}")
        
        print(f"出力ディレクトリ: {self.output_dir if self.output_dir else '未指定'}")
        print(f"ログモード: {'詳細表示' if self.verbose else '簡潔表示'}")
        print("==================")


def create_mvp_config_from_args(args) -> MVPConfig:
    """
    コマンドライン引数からMVP設定を作成
    
    Args:
        args: argparseのNamespace
        
    Returns:
        MVPConfig: 設定オブジェクト
    """
    # transcription_onlyが指定された場合は他の無効化フラグも自動設定
    disable_translation = getattr(args, 'transcription_only', False) or getattr(args, 'disable_translation', False)
    disable_docs_output = getattr(args, 'transcription_only', False) or getattr(args, 'disable_docs_output', False)
    
    config = MVPConfig(
        source_lang=args.source_lang,
        target_lang=args.target_lang,
        speaker_name=args.speaker_name,
        speech_model=getattr(args, 'model', 'large-v3'),
        google_docs_id=getattr(args, 'google_docs_id', None),
        output_dir=getattr(args, 'output_dir', None),
        disable_translation=disable_translation,
        disable_docs_output=disable_docs_output,
        transcription_only=getattr(args, 'transcription_only', False),
        verbose=getattr(args, 'verbose', False)
    )
    
    # input_deviceは明示的に指定された場合のみ上書き
    if hasattr(args, 'input_device') and args.input_device is not None:
        config.input_device = args.input_device
    
    return config


def test_config():
    """設定のテスト関数"""
    print("=== MVP設定テスト開始 ===")
    
    # テスト設定作成
    config = MVPConfig(
        source_lang="ja",
        target_lang="en", 
        speaker_name="テストユーザー"
    )
    
    # 設定表示
    config.print_config()
    
    # バリデーション
    is_valid, errors = config.validate()
    
    if is_valid:
        print("✅ 設定は有効です")
    else:
        print("❌ 設定エラー:")
        for error in errors:
            print(f"  - {error}")
    
    print("=== MVP設定テスト完了 ===")


if __name__ == "__main__":
    test_config() 