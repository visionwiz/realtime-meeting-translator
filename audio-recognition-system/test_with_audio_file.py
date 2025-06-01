#!/usr/bin/env python3
"""
録音ファイルを使用したテスト用サンプルスクリプト
リアルタイムミーティング翻訳システムの録音データ対応版

使用例:
1. 音声認識のみ（最高速）
   python test_with_audio_file.py

2. 翻訳付きテスト
   python test_with_audio_file.py --with-translation

3. Google Docs出力付きテスト
   python test_with_audio_file.py --with-docs YOUR_DOCS_ID

4. 高速テスト（2倍速）
   python test_with_audio_file.py --speed 2.0
"""

import os
import argparse
import subprocess
from pathlib import Path
from audio.file_audio_capture import validate_audio_file, get_supported_formats

def main():
    parser = argparse.ArgumentParser(description="録音ファイルテスト支援スクリプト")
    
    # 基本設定
    parser.add_argument(
        '--audio-file', 
        default='sample_audio.wav',
        help='テスト用音声ファイルパス（デフォルト: sample_audio.wav）'
    )
    parser.add_argument(
        '--source-lang', 
        default='ja',
        choices=['ja', 'en', 'ko', 'zh', 'es', 'fr', 'de'],
        help='発話言語（デフォルト: ja）'
    )
    parser.add_argument(
        '--target-lang', 
        default='en', 
        choices=['ja', 'en', 'ko', 'zh', 'es', 'fr', 'de'],
        help='翻訳先言語（デフォルト: en）'
    )
    parser.add_argument(
        '--speaker-name', 
        default='テストユーザー',
        help='発話者名（デフォルト: テストユーザー）'
    )
    
    # テストオプション
    parser.add_argument(
        '--speed', 
        type=float,
        default=1.0,
        help='再生速度倍率（デフォルト: 1.0、高速テスト: 2.0）'
    )
    parser.add_argument(
        '--with-translation',
        action='store_true',
        help='翻訳機能を有効化'
    )
    parser.add_argument(
        '--with-docs',
        help='Google Docs出力を有効化（DocsIDを指定）'
    )
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='詳細ログ表示'
    )
    
    args = parser.parse_args()
    
    print("🎵 録音ファイルテスト支援スクリプト")
    print("=" * 50)
    
    # 音声ファイル検証
    print(f"📁 音声ファイル: {args.audio_file}")
    
    if not Path(args.audio_file).exists():
        print(f"❌ ファイルが見つかりません: {args.audio_file}")
        print("\n📋 サポート音声形式:")
        for fmt in get_supported_formats():
            print(f"  - {fmt}")
        print("\n💡 テスト用音声ファイルを用意してから再実行してください")
        return
    
    # ファイル詳細情報表示
    is_valid, result = validate_audio_file(args.audio_file)
    if is_valid:
        print(f"✅ 音声ファイル詳細:")
        print(f"   長さ: {result['duration']:.1f}秒")
        print(f"   サンプリングレート: {result['sample_rate']}Hz")
        print(f"   チャンネル: {result['channels']}")
    else:
        print(f"❌ 音声ファイルエラー: {result}")
        return
    
    # テスト設定表示
    print(f"\n🔧 テスト設定:")
    print(f"   発話言語: {args.source_lang}")
    print(f"   翻訳先言語: {args.target_lang}")
    print(f"   発話者名: {args.speaker_name}")
    print(f"   再生速度: {args.speed}x")
    
    if args.speed != 1.0:
        estimated_time = result['duration'] / args.speed
        print(f"   予想実行時間: {estimated_time:.1f}秒")
    
    # 機能設定
    if args.with_translation:
        print("   翻訳機能: 有効")
    else:
        print("   翻訳機能: 無効（音声認識のみ）")
    
    if args.with_docs:
        print(f"   Google Docs出力: 有効（ID: {args.with_docs}）")
    else:
        print("   Google Docs出力: 無効")
    
    # main.pyコマンド構築
    cmd = [
        'python', 'main.py',
        '--source-lang', args.source_lang,
        '--target-lang', args.target_lang,
        '--speaker-name', args.speaker_name,
        '--audio-file', args.audio_file,
        '--playback-speed', str(args.speed)
    ]
    
    # オプション追加
    if not args.with_translation:
        cmd.append('--transcription-only')
    
    if args.with_docs:
        cmd.extend(['--google-docs-id', args.with_docs])
    else:
        cmd.append('--disable-docs-output')
    
    if args.verbose:
        cmd.append('--verbose')
    
    print(f"\n🚀 実行コマンド:")
    print(' '.join(cmd))
    print("\n" + "=" * 50)
    
    # 確認プロンプト
    response = input("テストを開始しますか？ [y/N]: ").strip().lower()
    if response not in ['y', 'yes']:
        print("❌ テストをキャンセルしました")
        return
    
    # main.py実行
    try:
        print("🎬 テスト開始...")
        subprocess.run(cmd)
        print("✅ テスト完了")
    except KeyboardInterrupt:
        print("\n⚠️ ユーザーによるテスト中断")
    except Exception as e:
        print(f"❌ テスト実行エラー: {e}")


if __name__ == "__main__":
    main() 