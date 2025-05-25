"""
既存Google Docsドキュメントへの追加書き込みテスト
MVP版でのリアルタイム追記機能の検証
"""

import os
import sys
from datetime import datetime
from typing import Optional

# Google API関連
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    print("✅ Google API ライブラリ インポート成功")
except ImportError as e:
    print(f"❌ Google API ライブラリ インポート失敗: {e}")
    sys.exit(1)

# Google Docs APIのスコープ
SCOPES = ['https://www.googleapis.com/auth/documents']

class ExistingDocsAppendTest:
    """既存Google Docsへの追加書き込みテストクラス"""
    
    def __init__(self, doc_id: str, token_path: str = "token.json"):
        self.doc_id = doc_id
        self.token_path = token_path
        self.service = None
        
        print(f"📄 テスト対象ドキュメントID: {doc_id}")
        print(f"🔗 URL: https://docs.google.com/document/d/{doc_id}/edit")
    
    def authenticate(self) -> bool:
        """認証（既存トークン使用）"""
        print("\n=== 認証処理 ===")
        
        try:
            if not os.path.exists(self.token_path):
                print(f"❌ トークンファイルが見つかりません: {self.token_path}")
                print("先に test_google_docs_simple.py を実行してください")
                return False
            
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
            
            if creds and creds.valid:
                print("✅ 既存トークンが有効です")
            elif creds and creds.expired and creds.refresh_token:
                print("🔄 トークンの更新中...")
                creds.refresh(Request())
                print("✅ トークン更新成功")
                
                # 更新されたトークンを保存
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())
            else:
                print("❌ 認証情報が無効です")
                return False
            
            # Google Docs APIサービス初期化
            self.service = build('docs', 'v1', credentials=creds)
            print("✅ Google Docs APIサービス初期化完了")
            return True
            
        except Exception as e:
            print(f"❌ 認証失敗: {e}")
            return False
    
    def test_read_existing_document(self) -> bool:
        """既存ドキュメントの読み取りテスト"""
        print("\n=== 既存ドキュメント読み取りテスト ===")
        
        if not self.service:
            print("❌ APIサービスが初期化されていません")
            return False
        
        try:
            # ドキュメントの情報を取得
            doc = self.service.documents().get(documentId=self.doc_id).execute()
            
            title = doc.get('title', 'タイトルなし')
            print(f"✅ ドキュメント読み取り成功")
            print(f"📋 タイトル: {title}")
            
            # 現在のコンテンツ長を確認
            content = doc.get('body', {}).get('content', [])
            end_index = 1
            for element in content:
                if 'endIndex' in element:
                    end_index = max(end_index, element['endIndex'])
            
            print(f"📏 現在のドキュメント長: {end_index} 文字")
            
            return True
            
        except HttpError as e:
            print(f"❌ ドキュメント読み取り失敗: {e}")
            if e.resp.status == 403:
                print("⚠️ アクセス権限がない可能性があります")
            elif e.resp.status == 404:
                print("⚠️ ドキュメントが見つかりません")
            return False
        except Exception as e:
            print(f"❌ 予期しないエラー: {e}")
            return False
    
    def test_append_to_document(self) -> bool:
        """ドキュメントへの追加書き込みテスト"""
        print("\n=== 追加書き込みテスト ===")
        
        if not self.service:
            print("❌ APIサービスが初期化されていません")
            return False
        
        try:
            # 現在のドキュメント状態を取得
            doc = self.service.documents().get(documentId=self.doc_id).execute()
            content = doc.get('body', {}).get('content', [])
            
            # 末尾位置を計算
            end_index = 1
            for element in content:
                if 'endIndex' in element:
                    end_index = max(end_index, element['endIndex'])
            
            print(f"📍 書き込み開始位置: {end_index - 1}")
            
            # 追加するテストコンテンツ
            test_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            append_content = f"""

=== 追加書き込みテスト ===
テスト実行時刻: {test_time}

🔄 MVP版リアルタイム書き込み機能テスト
この部分は既存ドキュメントに後から追加されました。

=== 模擬会議ログ ===
[{test_time}] テストユーザー:
原文(ja): これは追加書き込みのテストです。
翻訳(en): This is a test for additional writing.

[{test_time}] Test User:
原文(en): The append functionality is working correctly.
翻訳(ja): 追加機能が正常に動作しています。

✅ 既存ドキュメントへの追加書き込み: 成功
🎯 MVP版での継続的な会議ログ出力: 準備完了
"""
            
            # 書き込みリクエスト作成
            requests = [
                {
                    'insertText': {
                        'location': {
                            'index': end_index - 1
                        },
                        'text': append_content
                    }
                }
            ]
            
            print("📝 追加コンテンツを書き込み中...")
            result = self.service.documents().batchUpdate(
                documentId=self.doc_id,
                body={'requests': requests}
            ).execute()
            
            print("✅ 追加書き込み成功")
            print(f"🔗 更新確認URL: https://docs.google.com/document/d/{self.doc_id}/edit")
            
            return True
            
        except Exception as e:
            print(f"❌ 追加書き込み失敗: {e}")
            return False
    
    def test_multiple_appends(self) -> bool:
        """複数回の追加書き込みテスト（MVP版のリアルタイム出力シミュレーション）"""
        print("\n=== 複数回追加書き込みテスト ===")
        
        if not self.service:
            print("❌ APIサービスが初期化されていません")
            return False
        
        try:
            # 3回の追加書き込みをシミュレーション
            for i in range(1, 4):
                print(f"📝 追加書き込み {i}/3 実行中...")
                
                # 現在のドキュメント状態を取得
                doc = self.service.documents().get(documentId=self.doc_id).execute()
                content = doc.get('body', {}).get('content', [])
                
                # 末尾位置を計算
                end_index = 1
                for element in content:
                    if 'endIndex' in element:
                        end_index = max(end_index, element['endIndex'])
                
                # 追加コンテンツ
                test_time = datetime.now().strftime("%H:%M:%S")
                append_content = f"""
[{test_time}] 発話者{i}:
原文: これは{i}回目の追加書き込みテストです。
翻訳: This is the {i}th additional writing test.
"""
                
                # 書き込み実行
                requests = [
                    {
                        'insertText': {
                            'location': {
                                'index': end_index - 1
                            },
                            'text': append_content
                        }
                    }
                ]
                
                self.service.documents().batchUpdate(
                    documentId=self.doc_id,
                    body={'requests': requests}
                ).execute()
                
                print(f"✅ 追加書き込み {i}/3 完了")
            
            print("🎉 複数回追加書き込みテスト成功")
            print("✅ MVP版でのリアルタイム出力機能: 動作確認完了")
            
            return True
            
        except Exception as e:
            print(f"❌ 複数回追加書き込み失敗: {e}")
            return False
    
    def run_full_append_test(self) -> bool:
        """追加書き込み機能の全テスト実行"""
        print("🔄 既存ドキュメント追加書き込み全テスト開始")
        print("=" * 60)
        
        # 認証
        if not self.authenticate():
            print("\n❌ 認証失敗。テストを中止します。")
            return False
        
        # 既存ドキュメント読み取り
        if not self.test_read_existing_document():
            print("\n❌ ドキュメント読み取り失敗。追加書き込みテストを中止します。")
            return False
        
        # 追加書き込み
        if not self.test_append_to_document():
            print("\n❌ 追加書き込み失敗。")
            return False
        
        # 複数回追加書き込み
        if not self.test_multiple_appends():
            print("\n❌ 複数回追加書き込み失敗。")
            return False
        
        # 全テスト成功
        print("\n" + "=" * 60)
        print("🎉 既存ドキュメント追加書き込み全テスト成功！")
        print("✅ MVP版でのリアルタイム会議ログ出力機能: 準備完了")
        print(f"📋 更新されたドキュメント: https://docs.google.com/document/d/{self.doc_id}/edit")
        print("=" * 60)
        
        return True


def main():
    """メイン関数"""
    print("既存Google Docsドキュメント追加書き込みテストツール")
    print("MVP版リアルタイム出力機能の検証")
    
    # ドキュメントIDの指定
    if len(sys.argv) > 1:
        doc_id = sys.argv[1]
    else:
        # デフォルトのテストドキュメントID
        doc_id = "1pvuItqPAg54KZ_oEW7YyViwpvnyWgJJjUYrRpi_zrew"
    
    # テスト実行
    tester = ExistingDocsAppendTest(doc_id)
    success = tester.run_full_append_test()
    
    if success:
        print("\n🎯 次のステップ:")
        print("1. Claude APIキーの設定")
        print("2. main_mvp.py での統合テスト")
        print("3. 音声認識→翻訳→Google Docs出力の全体テスト")
        sys.exit(0)
    else:
        print("\n🔧 トラブルシューティング:")
        print("1. ドキュメントのアクセス権限確認")
        print("2. ドキュメントIDの確認")
        print("3. 認証トークンの更新")
        sys.exit(1)


if __name__ == "__main__":
    main() 