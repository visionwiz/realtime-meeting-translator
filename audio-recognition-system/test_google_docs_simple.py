"""
Google Docs API 簡易テストスクリプト
MVP開発前の不確実性排除のためのテスト

段階的テスト:
1. 認証テスト
2. API接続テスト  
3. ドキュメント作成テスト
4. 書き込みテスト
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
    print("pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib google-auth でインストールしてください")
    sys.exit(1)

# Google Docs APIのスコープ
SCOPES = ['https://www.googleapis.com/auth/documents']

class GoogleDocsSimpleTest:
    """Google Docs API簡易テストクラス"""
    
    def __init__(self, credentials_path: str = "credentials.json", token_path: str = "token.json"):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = None
        
        print(f"📁 認証ファイルパス: {credentials_path}")
        print(f"📁 トークンファイルパス: {token_path}")
    
    def test_step1_authentication(self) -> bool:
        """Step 1: 認証テスト"""
        print("\n=== Step 1: 認証テスト ===")
        
        try:
            creds = None
            
            # 既存トークンファイルをチェック
            if os.path.exists(self.token_path):
                print(f"🔍 既存トークンファイル発見: {self.token_path}")
                creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)
                
                if creds and creds.valid:
                    print("✅ 既存トークンが有効です")
                    self.service = build('docs', 'v1', credentials=creds)
                    return True
                
                if creds and creds.expired and creds.refresh_token:
                    print("🔄 トークンの更新中...")
                    try:
                        creds.refresh(Request())
                        print("✅ トークン更新成功")
                        
                        # 更新されたトークンを保存
                        with open(self.token_path, 'w') as token:
                            token.write(creds.to_json())
                        
                        self.service = build('docs', 'v1', credentials=creds)
                        return True
                    except Exception as e:
                        print(f"⚠️ トークン更新失敗: {e}")
                        creds = None
            
            # 新規認証が必要
            if not creds:
                if not os.path.exists(self.credentials_path):
                    print(f"❌ 認証ファイルが見つかりません: {self.credentials_path}")
                    print("\n📋 Google Cloud Console での設定手順:")
                    print("1. https://console.cloud.google.com/ にアクセス")
                    print("2. Google Docs API を有効化")
                    print("3. OAuth 2.0 認証情報を作成（デスクトップアプリケーション）")
                    print("4. credentials.json をダウンロードしてプロジェクトルートに配置")
                    return False
                
                print("🌐 新規OAuth認証を開始します...")
                print("ブラウザが開きます。Googleアカウントでログインして認証してください。")
                
                flow = InstalledAppFlow.from_client_secrets_file(self.credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
                
                # トークンを保存
                with open(self.token_path, 'w') as token:
                    token.write(creds.to_json())
                
                print("✅ 新規認証完了、トークンを保存しました")
            
            # Google Docs APIサービス初期化
            self.service = build('docs', 'v1', credentials=creds)
            print("✅ Google Docs APIサービス初期化完了")
            return True
            
        except Exception as e:
            print(f"❌ 認証テスト失敗: {e}")
            return False
    
    def test_step2_api_connection(self) -> bool:
        """Step 2: API接続テスト"""
        print("\n=== Step 2: API接続テスト ===")
        
        if not self.service:
            print("❌ APIサービスが初期化されていません")
            return False
        
        try:
            # ダミードキュメントへのアクセス試行で接続テスト
            dummy_doc_id = "1" * 44  # 44文字のダミーID
            try:
                self.service.documents().get(documentId=dummy_doc_id).execute()
            except HttpError as e:
                if e.resp.status == 404:
                    print("✅ API接続テスト成功（404エラーは期待される結果）")
                    return True
                else:
                    print(f"❌ API接続エラー: {e}")
                    return False
            
            # 予期しない成功（ダミーIDが実在することは稀）
            print("⚠️ ダミーIDが実在するドキュメントでした（稀な状況）")
            return True
            
        except Exception as e:
            print(f"❌ API接続テスト失敗: {e}")
            return False
    
    def test_step3_create_test_document(self) -> Optional[str]:
        """Step 3: テスト用ドキュメント作成"""
        print("\n=== Step 3: テストドキュメント作成 ===")
        
        if not self.service:
            print("❌ APIサービスが初期化されていません")
            return None
        
        try:
            # テストドキュメントを作成
            title = f"MVP音声認識システム テスト - {datetime.now().strftime('%Y%m%d_%H%M%S')}"
            document = {
                'title': title
            }
            
            print(f"📄 ドキュメント作成中: {title}")
            doc = self.service.documents().create(body=document).execute()
            doc_id = doc.get('documentId')
            
            print(f"✅ テストドキュメント作成成功")
            print(f"📋 ドキュメントID: {doc_id}")
            print(f"🔗 URL: https://docs.google.com/document/d/{doc_id}/edit")
            
            return doc_id
            
        except Exception as e:
            print(f"❌ ドキュメント作成失敗: {e}")
            return None
    
    def test_step4_write_to_document(self, doc_id: str) -> bool:
        """Step 4: ドキュメント書き込みテスト"""
        print("\n=== Step 4: ドキュメント書き込みテスト ===")
        
        if not self.service:
            print("❌ APIサービスが初期化されていません")
            return False
        
        if not doc_id:
            print("❌ ドキュメントIDが指定されていません")
            return False
        
        try:
            # テスト用のテキストを準備
            test_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            test_content = f"""MVP版 Google Docs API 書き込みテスト

テスト実行時刻: {test_time}

=== 基本書き込みテスト ===
このテキストが正常に書き込まれていれば、Google Docs APIの基本機能は動作しています。

=== 日本語テスト ===
こんにちは、Google Docs API！
音声認識からの日本語テキストが正常に書き込まれることを確認します。

=== 英語テスト ===
Hello, Google Docs API!
This is a test for English text input from speech recognition system.

=== MVP開発への準備完了 ===
✅ 認証: 成功
✅ API接続: 成功  
✅ ドキュメント作成: 成功
✅ テキスト書き込み: 成功

次のステップ: main_mvp.py での統合テスト
"""
            
            # ドキュメントの現在の長さを取得
            doc = self.service.documents().get(documentId=doc_id).execute()
            content = doc.get('body', {}).get('content', [])
            
            # 末尾位置を計算
            end_index = 1
            for element in content:
                if 'endIndex' in element:
                    end_index = max(end_index, element['endIndex'])
            
            # 書き込みリクエスト作成
            requests = [
                {
                    'insertText': {
                        'location': {
                            'index': end_index - 1
                        },
                        'text': test_content
                    }
                }
            ]
            
            print("📝 テストコンテンツを書き込み中...")
            result = self.service.documents().batchUpdate(
                documentId=doc_id,
                body={'requests': requests}
            ).execute()
            
            print("✅ ドキュメント書き込み成功")
            print(f"🔗 結果確認URL: https://docs.google.com/document/d/{doc_id}/edit")
            
            return True
            
        except Exception as e:
            print(f"❌ ドキュメント書き込み失敗: {e}")
            return False
    
    def run_full_test(self) -> bool:
        """全ステップの統合テスト実行"""
        print("🚀 Google Docs API 全ステップテスト開始")
        print("=" * 50)
        
        # Step 1: 認証
        if not self.test_step1_authentication():
            print("\n❌ 認証テストで失敗。後続のテストは実行できません。")
            return False
        
        # Step 2: API接続
        if not self.test_step2_api_connection():
            print("\n❌ API接続テストで失敗。後続のテストは実行できません。")
            return False
        
        # Step 3: ドキュメント作成
        doc_id = self.test_step3_create_test_document()
        if not doc_id:
            print("\n❌ ドキュメント作成テストで失敗。書き込みテストは実行できません。")
            return False
        
        # Step 4: 書き込み
        if not self.test_step4_write_to_document(doc_id):
            print("\n❌ 書き込みテストで失敗。")
            return False
        
        # 全テスト成功
        print("\n" + "=" * 50)
        print("🎉 Google Docs API 全ステップテスト成功！")
        print("✅ MVP開発でのGoogle Docs機能使用の準備完了")
        print(f"📋 テストドキュメント: https://docs.google.com/document/d/{doc_id}/edit")
        print("=" * 50)
        
        return True


def main():
    """メイン関数"""
    print("Google Docs API 簡易テストツール")
    print("MVP開発前の不確実性排除テスト")
    
    # コマンドライン引数の処理
    credentials_path = "credentials.json"
    if len(sys.argv) > 1:
        credentials_path = sys.argv[1]
    
    # テスト実行
    tester = GoogleDocsSimpleTest(credentials_path)
    success = tester.run_full_test()
    
    if success:
        print("\n🎯 次のステップ:")
        print("1. main_mvp.py でのGoogle Docs統合テスト")
        print("2. Claude APIキーの設定")
        print("3. MVP版システムの全体テスト")
        sys.exit(0)
    else:
        print("\n🔧 トラブルシューティング:")
        print("1. Google Cloud Console でのAPI設定確認")
        print("2. credentials.json ファイルの配置確認")  
        print("3. インターネット接続の確認")
        sys.exit(1)


if __name__ == "__main__":
    main() 