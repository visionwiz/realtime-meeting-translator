"""
基本的なGoogle Docs出力モジュール（MVP版）
シンプルなテキスト追記機能を提供

MVP戦略: 複雑なフォーマットは後回し、確実な基本出力を優先
"""

import os
import logging
import pickle
import time
import threading
import queue
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass

# Google API関連
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from http.client import IncompleteRead
import socket

# ログ設定
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Google Docs APIのスコープ
SCOPES = ['https://www.googleapis.com/auth/documents']

# リトライ設定
MAX_RETRIES = 3
RETRY_DELAY = 1.0  # 秒

# レート制限設定（Google Docs API制限への対応）
MIN_REQUEST_INTERVAL = 0.5  # 最小リクエスト間隔（秒）
MAX_CONCURRENT_REQUESTS = 1  # 同時リクエスト数制限


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
        
        # レート制限制御
        self.last_request_time = 0
        self.request_lock = threading.Lock()  # リクエストの同期化
        self.request_queue = queue.Queue()  # リクエストキューイング
        
        # 認証とサービス初期化
        self._authenticate()
        
        # リクエスト処理スレッド開始
        self._start_request_processor()
        
    def _start_request_processor(self):
        """リクエスト処理スレッドを開始"""
        def process_requests():
            while True:
                try:
                    # キューからリクエストを取得（1秒タイムアウト）
                    request_item = self.request_queue.get(timeout=1.0)
                    if request_item is None:  # 終了シグナル
                        break
                    
                    operation, result_callback = request_item
                    
                    # レート制限チェック
                    with self.request_lock:
                        current_time = time.time()
                        time_since_last = current_time - self.last_request_time
                        if time_since_last < MIN_REQUEST_INTERVAL:
                            sleep_time = MIN_REQUEST_INTERVAL - time_since_last
                            logger.debug(f"レート制限待機: {sleep_time:.2f}秒")
                            time.sleep(sleep_time)
                        
                        self.last_request_time = time.time()
                    
                    # リクエスト実行
                    try:
                        result = operation()
                        if result_callback:
                            result_callback(result, None)
                    except Exception as e:
                        if result_callback:
                            result_callback(None, e)
                        logger.error(f"キューイングされたリクエストでエラー: {e}")
                    
                    self.request_queue.task_done()
                    
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"リクエスト処理スレッドでエラー: {e}")
        
        thread = threading.Thread(target=process_requests, daemon=True)
        thread.start()
    
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
    
    def _execute_with_retry(self, operation, operation_name: str, max_retries: int = MAX_RETRIES):
        """
        Google Docs API操作をリトライ機能付きで実行
        
        Args:
            operation: 実行する操作（callable）
            operation_name: 操作名（ログ用）
            max_retries: 最大リトライ回数
            
        Returns:
            操作の結果
        """
        last_exception = None
        
        for attempt in range(max_retries + 1):
            try:
                # レート制限チェック
                with self.request_lock:
                    current_time = time.time()
                    time_since_last = current_time - self.last_request_time
                    if time_since_last < MIN_REQUEST_INTERVAL:
                        sleep_time = MIN_REQUEST_INTERVAL - time_since_last
                        logger.debug(f"レート制限待機 ({operation_name}): {sleep_time:.2f}秒")
                        time.sleep(sleep_time)
                    
                    self.last_request_time = time.time()
                
                return operation()
                
            except (IncompleteRead, socket.timeout, ConnectionError) as e:
                last_exception = e
                if attempt < max_retries:
                    logger.warning(f"{operation_name}でネットワークエラー (試行 {attempt + 1}/{max_retries + 1}): {e}")
                    time.sleep(RETRY_DELAY * (attempt + 1))  # 指数バックオフ
                    continue
                else:
                    logger.error(f"{operation_name}で最大リトライ回数に達しました: {e}")
                    raise
                    
            except HttpError as e:
                if e.resp.status == 429:  # レート制限エラー
                    last_exception = e
                    wait_time = (attempt + 1) * 2  # より長い待機時間
                    logger.warning(f"{operation_name}でレート制限エラー (試行 {attempt + 1}/{max_retries + 1}): {wait_time}秒待機")
                    time.sleep(wait_time)
                    continue
                elif e.resp.status in [500, 502, 503, 504]:  # サーバーエラーはリトライ
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(f"{operation_name}でサーバーエラー (試行 {attempt + 1}/{max_retries + 1}): {e}")
                        time.sleep(RETRY_DELAY * (attempt + 1))
                        continue
                    else:
                        logger.error(f"{operation_name}で最大リトライ回数に達しました: {e}")
                        raise
                else:
                    # クライアントエラーはリトライしない
                    raise
                    
            except Exception as e:
                # 予期しないエラーは1回だけリトライ
                last_exception = e
                if attempt == 0:
                    logger.warning(f"{operation_name}で予期しないエラー (リトライします): {e}")
                    time.sleep(RETRY_DELAY)
                    continue
                else:
                    logger.error(f"{operation_name}で予期しないエラー: {e}")
                    raise
        
        # ここには到達しないはずだが、安全のため
        raise last_exception if last_exception else Exception(f"{operation_name}で不明なエラー")

    def insert_placeholder(self, speaker_name: str, placeholder_id: str) -> Optional[int]:
        """
        プレースホルダーをGoogle Docsに挿入（レート制限対応版）
        
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
            
            def _insert_operation():
                # ドキュメントの末尾位置を取得（安全性を向上）
                doc = self.service.documents().get(documentId=self.document_id).execute()
                if not doc:
                    raise ValueError("ドキュメントの取得に失敗しました")
                    
                content = doc.get('body', {}).get('content', [])
                
                # より安全な末尾位置計算
                end_index = 1
                for element in content:
                    if 'endIndex' in element:
                        end_index = max(end_index, element['endIndex'])
                
                # 挿入位置を安全に設定（最低でも1、最大でもend_index-1）
                insert_index = max(1, min(end_index - 1, end_index - 1))
                
                # プレースホルダーを挿入
                requests = [
                    {
                        'insertText': {
                            'location': {
                                'index': insert_index
                            },
                            'text': placeholder_text
                        }
                    }
                ]
                
                result = self.service.documents().batchUpdate(
                    documentId=self.document_id,
                    body={'requests': requests}
                ).execute()
                
                return insert_index
            
            insert_position = self._execute_with_retry(_insert_operation, "プレースホルダー挿入")
            logger.info(f"プレースホルダー挿入完了: {placeholder_id}")
            return insert_position
            
        except HttpError as e:
            if "insertion index must be inside the bounds" in str(e):
                logger.warning(f"プレースホルダー挿入位置エラー、フォールバック処理: {e}")
                # フォールバック: シンプルな末尾追加
                try:
                    simple_text = f"\n[{datetime.now().strftime('%H:%M:%S')}] {speaker_name}: 🔄 翻訳中... (ID: {placeholder_id})\n"
                    return self._simple_append_text(simple_text)
                except Exception as fallback_error:
                    logger.error(f"フォールバック処理も失敗: {fallback_error}")
                    return None
            else:
                logger.error(f"プレースホルダー挿入HTTPエラー: {e}")
                return None
        except Exception as e:
            logger.error(f"プレースホルダー挿入エラー: {e}")
            return None
    
    def _simple_append_text(self, text: str) -> Optional[int]:
        """シンプルなテキスト末尾追加（フォールバック用）"""
        try:
            doc = self.service.documents().get(documentId=self.document_id).execute()
            content = doc.get('body', {}).get('content', [])
            
            # 最も安全な末尾位置を取得
            end_index = 1
            for element in content:
                if 'endIndex' in element:
                    end_index = max(end_index, element['endIndex'])
            
            # 最低限のテキストを挿入
            requests = [
                {
                    'insertText': {
                        'location': {
                            'index': max(1, end_index - 1)
                        },
                        'text': text
                    }
                }
            ]
            
            self.service.documents().batchUpdate(
                documentId=self.document_id,
                body={'requests': requests}
            ).execute()
            
            return end_index - 1
            
        except Exception as e:
            logger.error(f"シンプル追加でもエラー: {e}")
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
            def _update_operation():
                # ドキュメント内容を取得
                doc = self.service.documents().get(documentId=self.document_id).execute()
                if not doc:
                    raise ValueError("ドキュメントの取得に失敗しました")
                    
                content = doc.get('body', {}).get('content', [])
                
                # プレースホルダーを検索（改善版）
                target_text = f"🔄 Translating... / 翻訳中... (ID: {placeholder_id})"
                
                # ドキュメント全体のテキストを結合してプレースホルダーの位置を特定
                full_text = ""
                text_elements = []
                
                for element in content:
                    if 'paragraph' in element:
                        for text_run in element.get('paragraph', {}).get('elements', []):
                            if 'textRun' in text_run and 'content' in text_run['textRun']:
                                text_content = text_run['textRun'].get('content', '')
                                full_text += text_content
                                text_elements.append({
                                    'content': text_content,
                                    'startIndex': text_run.get('startIndex', 0),
                                    'endIndex': text_run.get('endIndex', 0)
                                })
                
                # プレースホルダー行の開始位置と終了位置を特定
                placeholder_start_pos = full_text.find(target_text)
                if placeholder_start_pos == -1:
                    # より緩い検索を試行（IDのみで検索）
                    fallback_text = f"(ID: {placeholder_id})"
                    placeholder_start_pos = full_text.find(fallback_text)
                    if placeholder_start_pos == -1:
                        logger.warning(f"プレースホルダーが見つかりません: {placeholder_id}")
                        logger.debug(f"検索対象テキスト: {target_text}")
                        logger.debug(f"フォールバック検索テキスト: {fallback_text}")
                        logger.debug(f"ドキュメント内容（最初の500文字）: {full_text[:500]}")
                        logger.debug(f"ドキュメント内容（末尾500文字）: {full_text[-500:]}")
                        logger.debug(f"アクティブなプレースホルダー検索:")
                        # 現在ドキュメント内にあるプレースホルダーを検索
                        import re
                        placeholder_pattern = r'\(ID: ([a-f0-9]{8})\)'
                        found_placeholders = re.findall(placeholder_pattern, full_text)
                        if found_placeholders:
                            logger.debug(f"ドキュメント内で見つかったプレースホルダーID: {found_placeholders}")
                        else:
                            logger.debug("ドキュメント内にプレースホルダーが見つかりませんでした")
                        return False
                    
                    # 行の開始位置まで戻る
                    line_start = full_text.rfind('\n', 0, placeholder_start_pos)
                    if line_start == -1:
                        line_start = 0
                    else:
                        line_start += 1
                    
                    # 行の終了位置を見つける
                    line_end = full_text.find('\n', placeholder_start_pos)
                    if line_end == -1:
                        line_end = len(full_text)
                    else:
                        line_end += 1  # 改行文字も含める
                    
                    placeholder_start_pos = line_start
                    placeholder_end_pos = line_end
                else:
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
                
                result = self.service.documents().batchUpdate(
                    documentId=self.document_id,
                    body={'requests': requests}
                ).execute()
                
                return True
            
            success = self._execute_with_retry(_update_operation, "プレースホルダー更新")
            if success:
                logger.info(f"プレースホルダー更新完了: {placeholder_id}")
            return success
            
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
            def _write_operation():
                # エントリーをテキスト形式に変換
                entry_text = self._format_entry(entry)
                
                # まずドキュメントの現在の長さを取得
                doc = self.service.documents().get(documentId=self.document_id).execute()
                if not doc:
                    raise ValueError("ドキュメントの取得に失敗しました")
                    
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
                
                return True
            
            success = self._execute_with_retry(_write_operation, "Google Docs書き込み")
            if success:
                logger.info(f"Google Docsに書き込み完了: {entry.speaker_name}")
            return success
            
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