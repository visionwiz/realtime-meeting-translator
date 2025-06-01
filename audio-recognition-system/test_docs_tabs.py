#!/usr/bin/env python3
"""
Google Docsタブ機能テストスクリプト
使用方法: python test_docs_tabs.py DOCUMENT_ID [TAB_ID]
"""

import sys
import os
from datetime import datetime

# プロジェクトルートをパスに追加
sys.path.append(os.path.join(os.path.dirname(__file__), 'output'))
from basic_google_docs_writer import BasicGoogleDocsWriter, MeetingEntry

def test_docs_tabs(document_id: str, tab_id: str = None):
    """Google Docsタブ機能をテスト"""
    
    print(f"=== Google Docsタブ機能テスト ===")
    print(f"ドキュメントID: {document_id}")
    if tab_id:
        print(f"タブID: {tab_id}")
    else:
        print("タブID: 未指定（デフォルトタブ）")
    print()
    
    try:
        # Google Docs Writer初期化
        print("1. Google Docs Writer初期化中...")
        writer = BasicGoogleDocsWriter()
        writer.set_document_id(document_id)
        
        if tab_id:
            writer.set_tab_id(tab_id)
        
        # アクセス確認
        print("2. ドキュメント・タブアクセス確認中...")
        if not writer.verify_document_access():
            print("❌ アクセス確認失敗")
            return False
        
        print("✅ アクセス確認成功")
        
        # テスト用セッションヘッダー書き込み
        print("3. セッションヘッダー書き込みテスト中...")
        session_info = {
            'source_lang': 'ja',
            'target_lang': 'en'
        }
        
        if writer.write_session_header(session_info):
            print("✅ セッションヘッダー書き込み成功")
        else:
            print("❌ セッションヘッダー書き込み失敗")
            return False
        
        # テスト用エントリー書き込み
        print("4. テストエントリー書き込み中...")
        test_entry = MeetingEntry(
            timestamp=datetime.now(),
            speaker_name="テストユーザー",
            original_text="これはGoogle Docsタブ機能のテストです。",
            translated_text="This is a test of Google Docs tabs functionality.",
            source_lang="ja",
            target_lang="en"
        )
        
        if writer.write_meeting_entry(test_entry):
            print("✅ テストエントリー書き込み成功")
        else:
            print("❌ テストエントリー書き込み失敗")
            return False
        
        print()
        print("🎉 すべてのテストが成功しました！")
        if tab_id:
            print(f"📄 指定されたタブ '{tab_id}' への書き込みが正常に動作しています")
        else:
            print("📄 デフォルトタブへの書き込みが正常に動作しています")
        
        return True
        
    except Exception as e:
        print(f"❌ テスト中にエラーが発生しました: {e}")
        return False

def main():
    """メイン関数"""
    if len(sys.argv) < 2:
        print("使用方法: python test_docs_tabs.py DOCUMENT_ID [TAB_ID]")
        print()
        print("例:")
        print("  python test_docs_tabs.py 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms")
        print("  python test_docs_tabs.py 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms t.0-0")
        sys.exit(1)
    
    document_id = sys.argv[1]
    tab_id = sys.argv[2] if len(sys.argv) > 2 else None
    
    success = test_docs_tabs(document_id, tab_id)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main() 