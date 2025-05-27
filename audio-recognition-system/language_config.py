from dataclasses import dataclass

@dataclass
class LanguageConfig:
    """言語設定を管理するデータクラス"""
    source_lang: str  # 音声認識および翻訳元の言語
    target_lang: str  # 翻訳先言語
    
    def get_source_language(self) -> str:
        """ソース言語コードを取得"""
        return self.source_lang
    
    def get_source_language_code(self) -> str:
        """Google Cloud Speech-to-Text用のソース言語コードを取得"""
        lang_mapping = {
            'ja': 'ja-JP',
            'en': 'en-US', 
            'ko': 'ko-KR',
            'zh': 'zh-CN',
            'es': 'es-ES',
            'fr': 'fr-FR',
            'de': 'de-DE'
        }
        return lang_mapping.get(self.source_lang, 'en-US')
    
    def get_target_language(self) -> str:
        """ターゲット言語コードを取得"""
        return self.target_lang
    
    @staticmethod
    def get_language_name(lang_code: str) -> str:
        """言語コードから言語名を取得"""
        LANGUAGE_NAMES = {
            'ja': '日本語',
            'en': '英語',
            'zh': '中国語',
            'ko': '韓国語',
            'fr': 'フランス語',
            'de': 'ドイツ語',
            'es': 'スペイン語',
            'it': 'イタリア語',
        }
        return LANGUAGE_NAMES.get(lang_code, lang_code)

