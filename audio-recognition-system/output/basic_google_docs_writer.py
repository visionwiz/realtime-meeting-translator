"""
基本的なGoogle Docs出力モジュール（MVP版）
シンプルなテキスト追記機能を提供

MVP戦略: 複雑なフォーマットは後回し、確実な基本出力を優先
"""

import os
import logging
import pickle
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

# Google API関連
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Google Docs APIのスコープ
SCOPES = ['https://www.googleapis.com/auth/documents']


@dataclass
class MeetingEntry:
    """会議エントリーデータクラス"""
    timestamp: datetime
    speaker_name: str
    original_text: str
    translated_text: str
    source_lang: str
    target_lang: str


class BasicGoogleDocsWriter:
    """基本的なGoogle Docs出力クラス（MVP版）"""
    
    def __init__(self, credentials_path: str = "credentials.json", token_path: str = "token.json"):
        """
        Google Docs出力器の初期化
        
        Args:
            credentials_path: OAuth認証ファイルのパス
            token_path: トークンファイルのパス
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        self.document_id = None
        
        # 認証とサービス初期化
        self._authenticate()
        
    def _authenticate(self):
        """Google OAuth認証を実行"""
        creds = None
        
        # 既存のトークンファイルをチェック
        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
        
        # 有効な認証情報がない場合、新しく認証
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("Google認証トークンを更新しました")
                except Exception as e:
                    logger.warning(f"トークン更新に失敗: {e}")
                    creds = None
            
            if not creds:
                if not os.path.exists(self.credentials_path):
                    raise FileNotFoundError(f"認証ファイルが見つかりません: {self.credentials_path}")
                
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
                logger.info("新しいGoogle認証を完了しました")
            
            # トークンを保存
            with open(self.token_path, 'w') as token:
                token.write(creds.to_json())
        
        # Google Docs APIサービスを初期化
        try:
            self.service = build('docs', 'v1', credentials=creds)
            logger.info("Google Docs APIサービス初期化完了")
        except Exception as e:
            logger.error(f"Google Docs APIサービス初期化失敗: {e}")
            raise
    
    def set_document_id(self, document_id: str):
        """
        対象のGoogle DocsドキュメントIDを設定
        
        Args:
            document_id: Google DocsのドキュメントID
        """
        self.document_id = document_id
        logger.info(f"Google DocsドキュメントID設定: {document_id}")
    
    def verify_document_access(self) -> bool:
        """
        ドキュメントアクセス可能性の確認（テスト結果を踏まえた追加機能）
        
        Returns:
            bool: アクセス可能の場合True
        """
        if not self.document_id:
            logger.error("ドキュメントIDが設定されていません")
            return False
        
        if not self.service:
            logger.error("Google Docs APIサービスが初期化されていません")
            return False
        
        try:
            # ドキュメントの基本情報を取得してアクセス確認
            doc = self.service.documents().get(documentId=self.document_id).execute()
            title = doc.get('title', 'タイトルなし')
            logger.info(f"✅ ドキュメントアクセス確認成功: {title}")
            return True
            
        except HttpError as e:
            if e.resp.status == 403:
                logger.error(f"❌ ドキュメントアクセス権限なし: {self.document_id}")
            elif e.resp.status == 404:
                logger.error(f"❌ ドキュメント未発見: {self.document_id}")
            else:
                logger.error(f"❌ ドキュメントアクセスエラー: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ ドキュメントアクセス予期しないエラー: {e}")
            return False
    
    def test_connection(self) -> bool:
        """
        Google Docs APIの接続テスト
        
        Returns:
            bool: 接続成功の場合True
        """
        if not self.service:
            logger.error("Google Docs APIサービスが初期化されていません")
            return False
        
        try:
            # 簡単なAPIコールでテスト
            logger.info("Google Docs API接続テスト実行中...")
            
            # ダミーのドキュメント情報取得試行（エラーは無視）
            test_doc_id = "1" * 44  # 44文字のダミーID
            try:
                self.service.documents().get(documentId=test_doc_id).execute()
            except HttpError as e:
                if e.resp.status == 404:
                    # 404は期待される結果（ダミーIDなので）
                    logger.info("Google Docs API接続テスト成功")
                    return True
                else:
                    # その他のエラーは接続問題の可能性
                    logger.error(f"Google Docs API接続テスト失敗: {e}")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Google Docs API接続テストでエラー: {e}")
            return False
    
    def insert_placeholder(self, speaker_name: str, placeholder_id: str) -> Optional[int]:
        """
        プレースホルダーをGoogle Docsに挿入
        
        Args:
            speaker_name: 発話者名
            placeholder_id: プレースホルダーの一意ID
            
        Returns:
            Optional[int]: 挿入位置のインデックス（失敗時はNone）
        """
        if not self.document_id or not self.service:
            logger.error("ドキュメントIDまたはサービスが初期化されていません")
            return None
        
        try:
            timestamp_str = datetime.now().strftime("%H:%M:%S")
            # プレースホルダーを独立した段落として作成
            placeholder_text = f"""[{timestamp_str}] {speaker_name}:
🔄 Translating... / 翻訳中... (ID: {placeholder_id})

"""
            
            # ドキュメントの末尾位置を取得
            doc = self.service.documents().get(documentId=self.document_id).execute()
            content = doc.get('body', {}).get('content', [])
            
            end_index = 1
            for element in content:
                if 'endIndex' in element:
                    end_index = max(end_index, element['endIndex'])
            
            # プレースホルダーを挿入
            requests = [
                {
                    'insertText': {
                        'location': {
                            'index': end_index - 1
                        },
                        'text': placeholder_text
                    }
                }
            ]
            
            self.service.documents().batchUpdate(
                documentId=self.document_id,
                body={'requests': requests}
            ).execute()
            
            logger.info(f"プレースホルダー挿入完了: {placeholder_id}")
            return end_index - 1  # 挿入位置を返す
            
        except Exception as e:
            logger.error(f"プレースホルダー挿入エラー: {e}")
            return None
    
    def update_placeholder(self, placeholder_id: str, entry: MeetingEntry) -> bool:
        """
        プレースホルダーを実際の翻訳内容に置き換え
        
        Args:
            placeholder_id: 置き換え対象のプレースホルダーID
            entry: 会議エントリー
            
        Returns:
            bool: 更新成功の場合True
        """
        if not self.document_id or not self.service:
            logger.error("ドキュメントIDまたはサービスが初期化されていません")
            return False
        
        try:
            # ドキュメント内容を取得
            doc = self.service.documents().get(documentId=self.document_id).execute()
            content = doc.get('body', {}).get('content', [])
            
            # プレースホルダーを検索（改善版）
            target_text = f"🔄 Translating... / 翻訳中... (ID: {placeholder_id})"
            
            # ドキュメント全体のテキストを結合してプレースホルダーの位置を特定
            full_text = ""
            text_elements = []
            
            for element in content:
                if 'paragraph' in element:
                    for text_run in element.get('paragraph', {}).get('elements', []):
                        if 'textRun' in text_run:
                            text_content = text_run['textRun'].get('content', '')
                            full_text += text_content
                            text_elements.append({
                                'content': text_content,
                                'startIndex': text_run['startIndex'],
                                'endIndex': text_run['endIndex']
                            })
            
            # プレースホルダー行の開始位置と終了位置を特定
            placeholder_start_pos = full_text.find(target_text)
            if placeholder_start_pos == -1:
                logger.warning(f"プレースホルダーが見つかりません: {placeholder_id}")
                return False
            
            placeholder_end_pos = placeholder_start_pos + len(target_text)
            
            # プレースホルダー行の改行も含めて削除（次の改行文字まで）
            if placeholder_end_pos < len(full_text) and full_text[placeholder_end_pos] == '\n':
                placeholder_end_pos += 1
            
            # テキスト要素のインデックスから実際のドキュメント位置を計算
            doc_start_index = None
            doc_end_index = None
            current_pos = 0
            
            for text_elem in text_elements:
                elem_len = len(text_elem['content'])
                if doc_start_index is None and current_pos <= placeholder_start_pos < current_pos + elem_len:
                    # プレースホルダー開始位置
                    offset = placeholder_start_pos - current_pos
                    doc_start_index = text_elem['startIndex'] + offset
                
                if doc_end_index is None and current_pos < placeholder_end_pos <= current_pos + elem_len:
                    # プレースホルダー終了位置
                    offset = placeholder_end_pos - current_pos
                    doc_end_index = text_elem['startIndex'] + offset
                    break
                
                current_pos += elem_len
            
            if doc_start_index is None or doc_end_index is None:
                logger.warning(f"プレースホルダーの位置を特定できません: {placeholder_id}")
                return False
            
            # 翻訳内容のみを生成（タイムスタンプと発話者名は含めない）
            replacement_text = f"""({entry.source_lang}): {entry.original_text}
({entry.target_lang}): {entry.translated_text}"""
            
            # プレースホルダー行のみを削除して翻訳内容に置き換え
            requests = [
                {
                    'deleteContentRange': {
                        'range': {
                            'startIndex': doc_start_index,
                            'endIndex': doc_end_index
                        }
                    }
                },
                {
                    'insertText': {
                        'location': {
                            'index': doc_start_index
                        },
                        'text': replacement_text
                    }
                }
            ]
            
            self.service.documents().batchUpdate(
                documentId=self.document_id,
                body={'requests': requests}
            ).execute()
            
            logger.info(f"プレースホルダー更新完了: {placeholder_id}")
            return True
            
        except Exception as e:
            logger.error(f"プレースホルダー更新エラー: {e}")
            return False

    def write_meeting_entry(self, entry: MeetingEntry) -> bool:
        """
        会議エントリーをGoogle Docsに書き込み
        
        Args:
            entry: 会議エントリー
            
        Returns:
            bool: 書き込み成功の場合True
        """
        if not self.document_id:
            logger.error("Google DocsドキュメントIDが設定されていません")
            return False
        
        if not self.service:
            logger.error("Google Docs APIサービスが初期化されていません")
            return False
        
        try:
            # エントリーをテキスト形式に変換
            entry_text = self._format_entry(entry)
            
            # まずドキュメントの現在の長さを取得
            doc = self.service.documents().get(documentId=self.document_id).execute()
            content = doc.get('body', {}).get('content', [])
            
            # ドキュメントの末尾位置を計算
            end_index = 1
            for element in content:
                if 'endIndex' in element:
                    end_index = max(end_index, element['endIndex'])
            
            # 正しい位置に挿入（テスト結果を踏まえた改善）
            requests = [
                {
                    'insertText': {
                        'location': {
                            'index': end_index - 1  # 末尾の前に挿入
                        },
                        'text': entry_text
                    }
                }
            ]
            
            # バッチ更新実行
            result = self.service.documents().batchUpdate(
                documentId=self.document_id,
                body={'requests': requests}
            ).execute()
            
            logger.info(f"Google Docsに書き込み完了: {entry.speaker_name}")
            return True
            
        except HttpError as e:
            # テスト結果を踏まえた詳細なエラーハンドリング
            if e.resp.status == 403:
                logger.error(f"Google Docs書き込み権限エラー: ドキュメントへのアクセス権限がありません - {e}")
            elif e.resp.status == 404:
                logger.error(f"Google Docsドキュメント未発見エラー: ドキュメントID {self.document_id} が見つかりません - {e}")
            else:
                logger.error(f"Google Docs書き込みエラー: {e}")
            return False
        except Exception as e:
            logger.error(f"予期しないエラー: {e}")
            return False
    
    def _format_entry(self, entry: MeetingEntry) -> str:
        """
        会議エントリーをテキスト形式にフォーマット
        
        Args:
            entry: 会議エントリー
            
        Returns:
            str: フォーマット済みテキスト
        """
        # タイムスタンプは時刻のみ（日付部分は削除）
        timestamp_str = entry.timestamp.strftime("%H:%M:%S")
        
        # フォールバック書き込み用：完全なフォーマット
        formatted_text = f"""[{timestamp_str}] {entry.speaker_name}:
({entry.source_lang}): {entry.original_text}
({entry.target_lang}): {entry.translated_text}

"""
        
        return formatted_text
    
    def write_session_header(self, session_info: Dict[str, Any]) -> bool:
        """
        セッション開始時のヘッダーを書き込み
        
        Args:
            session_info: セッション情報
            
        Returns:
            bool: 書き込み成功の場合True
        """
        if not self.document_id:
            logger.error("Google DocsドキュメントIDが設定されていません")
            return False
        
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        speaker = session_info.get('speaker_name', 'Unknown')
        source_lang = session_info.get('source_lang', 'unknown')
        target_lang = session_info.get('target_lang', 'unknown')
        
        header_text = f"""
=== Real-time Meeting Translation Session Started / リアルタイム会議翻訳セッション開始 ===
Start Time / 開始時刻: {start_time}
Speaker / 発話者: {speaker}
Translation Direction / 翻訳方向: {source_lang} → {target_lang}
=======================================

"""
        
        try:
            # ドキュメントの末尾に追加
            doc = self.service.documents().get(documentId=self.document_id).execute()
            content = doc.get('body', {}).get('content', [])
            
            end_index = 1
            for element in content:
                if 'endIndex' in element:
                    end_index = max(end_index, element['endIndex'])
            
            requests = [
                {
                    'insertText': {
                        'location': {
                            'index': end_index - 1
                        },
                        'text': header_text
                    }
                }
            ]
            
            self.service.documents().batchUpdate(
                documentId=self.document_id,
                body={'requests': requests}
            ).execute()
            
            logger.info("セッションヘッダーをGoogle Docsに書き込み完了")
            return True
            
        except HttpError as e:
            # テスト結果を踏まえた詳細なエラーハンドリング
            if e.resp.status == 403:
                logger.error(f"セッションヘッダー権限エラー: ドキュメントへのアクセス権限がありません - {e}")
            elif e.resp.status == 404:
                logger.error(f"セッションヘッダードキュメント未発見エラー: ドキュメントID {self.document_id} が見つかりません - {e}")
            else:
                logger.error(f"セッションヘッダー書き込みエラー: {e}")
            return False
        except Exception as e:
            logger.error(f"セッションヘッダー予期しないエラー: {e}")
            return False


# MVP版テスト用の簡易関数
def test_google_docs_writer(document_id: str = None):
    """Google Docs出力器のテスト関数"""
    try:
        writer = BasicGoogleDocsWriter()
        
        # 接続テスト
        if not writer.test_connection():
            print("❌ Google Docs API接続に失敗しました")
            return
        
        print("✅ Google Docs API接続成功")
        
        if document_id:
            writer.set_document_id(document_id)
            
            # セッションヘッダーテスト
            session_info = {
                'speaker_name': 'テストユーザー',
                'source_lang': 'ja',
                'target_lang': 'en'
            }
            
            if writer.write_session_header(session_info):
                print("✅ セッションヘッダー書き込み成功")
            else:
                print("❌ セッションヘッダー書き込み失敗")
            
            # エントリー書き込みテスト
            test_entry = MeetingEntry(
                timestamp=datetime.now(),
                speaker_name="テストユーザー",
                original_text="こんにちは、テストです。",
                translated_text="Hello, this is a test.",
                source_lang="ja",
                target_lang="en"
            )
            
            if writer.write_meeting_entry(test_entry):
                print("✅ エントリー書き込み成功")
            else:
                print("❌ エントリー書き込み失敗")
        else:
            print("📝 ドキュメントIDが指定されていないため、書き込みテストはスキップ")
        
        print("=== Google Docs出力テスト完了 ===")
        
    except Exception as e:
        print(f"❌ Google Docs出力テストでエラー: {e}")


if __name__ == "__main__":
    import sys
    
    # コマンドライン引数でドキュメントIDを指定可能
    document_id = sys.argv[1] if len(sys.argv) > 1 else None
    test_google_docs_writer(document_id) 