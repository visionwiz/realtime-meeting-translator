"""
Claude 3.7 Sonnet翻訳モジュール（MVP版）
シンプルな単発翻訳機能を提供

MVP戦略: 複雑な文脈バッファリングは後回し、確実な基本翻訳を優先
"""

import anthropic
import time
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TranslationResult:
    """翻訳結果を格納するデータクラス"""
    original_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    timestamp: float
    success: bool
    error_message: Optional[str] = None


class ClaudeTranslator:
    """Claude 3.7 Sonnet翻訳クラス（MVP版）"""
    
    def __init__(self, api_key: str, model_name: str = "claude-3-7-sonnet-20250219"):
        """
        Claude翻訳器の初期化
        
        Args:
            api_key: Claude APIキー
            model_name: 使用するClaudeモデル名（MVP版は固定）
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model_name = model_name
        
        # シンプルな設定（MVP版）
        self.max_retries = 3
        self.retry_delay = 1.0
        
        logger.info(f"Claude翻訳器初期化完了: {model_name}")
    
    def translate(self, text: str, source_lang: str, target_lang: str) -> TranslationResult:
        """
        テキストを翻訳
        
        Args:
            text: 翻訳対象テキスト
            source_lang: 発話言語（ja, en等）
            target_lang: 翻訳先言語（ja, en等）
            
        Returns:
            TranslationResult: 翻訳結果
        """
        if not text.strip():
            return TranslationResult(
                original_text=text,
                translated_text="",
                source_lang=source_lang,
                target_lang=target_lang,
                timestamp=time.time(),
                success=True
            )
        
        # 言語名の正規化
        lang_names = self._get_language_names(source_lang, target_lang)
        
        # 翻訳プロンプト作成（MVP版: シンプル）
        prompt = self._create_translation_prompt(text, lang_names['source'], lang_names['target'])
        
        # 翻訳実行（リトライ機能付き）
        for attempt in range(self.max_retries):
            try:
                logger.info(f"翻訳実行中... (試行 {attempt + 1}/{self.max_retries})")
                
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=1000,
                    temperature=0.1,  # 一貫性を重視
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )
                
                translated_text = response.content[0].text.strip()
                
                logger.info(f"翻訳成功: '{text[:50]}...' -> '{translated_text[:50]}...'")
                
                return TranslationResult(
                    original_text=text,
                    translated_text=translated_text,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    timestamp=time.time(),
                    success=True
                )
                
            except anthropic.APIConnectionError as e:
                logger.warning(f"API接続エラー (試行 {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
                
            except anthropic.RateLimitError as e:
                logger.warning(f"レート制限エラー (試行 {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * 2)  # レート制限時は長めに待機
                    continue
                    
            except Exception as e:
                logger.error(f"翻訳エラー (試行 {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                    continue
        
        # 全ての試行が失敗した場合
        error_message = f"翻訳に失敗しました（{self.max_retries}回試行）"
        logger.error(error_message)
        
        return TranslationResult(
            original_text=text,
            translated_text=text,  # 失敗時は原文をそのまま返す
            source_lang=source_lang,
            target_lang=target_lang,
            timestamp=time.time(),
            success=False,
            error_message=error_message
        )
    
    def _create_translation_prompt(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        翻訳プロンプトを作成（MVP版: シンプル）
        
        Args:
            text: 翻訳対象テキスト
            source_lang: 発話言語名
            target_lang: 翻訳先言語名
            
        Returns:
            str: 翻訳プロンプト
        """
        return f"""以下の{source_lang}のテキストを{target_lang}に翻訳してください。

翻訳の際は以下の点に注意してください：
- 自然で読みやすい翻訳を心がける
- 会議での発話として適切な表現を使用
- 専門用語は文脈に応じて適切に翻訳
- 翻訳結果のみを出力（説明や注釈は不要）

翻訳対象テキスト:
{text}

翻訳結果:"""
    
    def _get_language_names(self, source_lang: str, target_lang: str) -> Dict[str, str]:
        """
        言語コードを言語名に変換
        
        Args:
            source_lang: 発話言語コード
            target_lang: 翻訳先言語コード
            
        Returns:
            Dict[str, str]: 言語名の辞書
        """
        lang_map = {
            'ja': '日本語',
            'en': '英語',
            'ko': '韓国語',
            'zh': '中国語',
            'es': 'スペイン語',
            'fr': 'フランス語',
            'de': 'ドイツ語'
        }
        
        return {
            'source': lang_map.get(source_lang, source_lang),
            'target': lang_map.get(target_lang, target_lang)
        }
    
    def test_connection(self) -> bool:
        """
        Claude API接続テスト
        
        Returns:
            bool: 接続成功の場合True
        """
        try:
            logger.info("Claude API接続テスト実行中...")
            
            test_result = self.translate("Hello", "en", "ja")
            
            if test_result.success:
                logger.info("Claude API接続テスト成功")
                return True
            else:
                logger.error("Claude API接続テスト失敗")
                return False
                
        except Exception as e:
            logger.error(f"Claude API接続テストでエラー: {e}")
            return False


# MVP版テスト用の簡易関数
def test_claude_translator(api_key: str):
    """Claude翻訳器のテスト関数"""
    translator = ClaudeTranslator(api_key)
    
    # 接続テスト
    if not translator.test_connection():
        print("❌ Claude API接続に失敗しました")
        return
    
    # 基本翻訳テスト
    test_cases = [
        ("こんにちは、今日の会議を始めましょう。", "ja", "en"),
        ("Thank you for organizing this meeting.", "en", "ja"),
        ("", "ja", "en"),  # 空文字テスト
    ]
    
    print("\n=== 翻訳テスト開始 ===")
    for text, source, target in test_cases:
        result = translator.translate(text, source, target)
        status = "✅" if result.success else "❌"
        print(f"{status} {source}→{target}: '{text}' -> '{result.translated_text}'")
    
    print("=== 翻訳テスト完了 ===")


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    api_key = os.getenv("CLAUDE_API_KEY")
    
    if api_key:
        test_claude_translator(api_key)
    else:
        print("❌ CLAUDE_API_KEY環境変数が設定されていません") 