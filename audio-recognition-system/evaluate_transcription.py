#!/usr/bin/env python3
"""
音声認識精度評価スクリプト
正解データと音声認識結果を比較してWER（Word Error Rate）を計算
"""

import re
import argparse
from pathlib import Path
from typing import List, Tuple
import difflib

def parse_transcript_file(file_path: str) -> List[Tuple[str, str]]:
    """
    音声認識結果ファイルまたは正解データファイルを解析
    Returns: [(timestamp, text), ...]
    """
    results = []
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    current_timestamp = None
    for line in lines:
        line = line.strip()
        
        # タイムスタンプ行の検出
        timestamp_match = re.match(r'\[(\d{2}:\d{2}:\d{2})\]', line)
        if timestamp_match:
            # 正解データ形式: [HH:MM:SS] テキスト
            if ' ' in line:
                timestamp = timestamp_match.group(1)
                text = line[timestamp_match.end():].strip()
                results.append((timestamp, text))
            else:
                # ログファイル形式: [HH:MM:SS] だけの行
                current_timestamp = timestamp_match.group(1)
        
        # 音声認識結果の検出
        elif line.startswith('認識結果(') and current_timestamp:
            # 認識結果(ja): テキスト 形式
            text_match = re.match(r'認識結果\([^)]+\):\s*(.+)', line)
            if text_match:
                text = text_match.group(1)
                results.append((current_timestamp, text))
                current_timestamp = None
    
    return results

def normalize_text(text: str) -> str:
    """テキスト正規化（比較用）"""
    # 句読点除去、スペース正規化
    text = re.sub(r'[。、．，]', '', text)
    text = re.sub(r'\s+', '', text)
    return text.lower()

def calculate_wer(reference: str, hypothesis: str) -> float:
    """Word Error Rate (WER) 計算"""
    ref_words = list(normalize_text(reference))
    hyp_words = list(normalize_text(hypothesis))
    
    # 編集距離計算
    d = [[0 for _ in range(len(hyp_words) + 1)] for _ in range(len(ref_words) + 1)]
    
    for i in range(len(ref_words) + 1):
        d[i][0] = i
    for j in range(len(hyp_words) + 1):
        d[0][j] = j
    
    for i in range(1, len(ref_words) + 1):
        for j in range(1, len(hyp_words) + 1):
            if ref_words[i-1] == hyp_words[j-1]:
                d[i][j] = d[i-1][j-1]
            else:
                d[i][j] = min(
                    d[i-1][j] + 1,      # 削除
                    d[i][j-1] + 1,      # 挿入
                    d[i-1][j-1] + 1     # 置換
                )
    
    # WER計算
    edit_distance = d[len(ref_words)][len(hyp_words)]
    wer = edit_distance / len(ref_words) if len(ref_words) > 0 else 0
    return wer

def compare_transcriptions(reference_file: str, hypothesis_file: str, verbose: bool = False):
    """音声認識結果と正解データを比較"""
    print(f"📊 音声認識精度評価")
    print(f"正解データ: {reference_file}")
    print(f"認識結果: {hypothesis_file}")
    print("=" * 60)
    
    # ファイル読み込み
    ref_data = parse_transcript_file(reference_file)
    hyp_data = parse_transcript_file(hypothesis_file)
    
    print(f"正解データ発話数: {len(ref_data)}")
    print(f"認識結果発話数: {len(hyp_data)}")
    print("-" * 60)
    
    # 時系列でマッチング
    total_wer = 0
    matched_pairs = 0
    
    for i, (ref_ts, ref_text) in enumerate(ref_data):
        # 対応する認識結果を検索（タイムスタンプ近似マッチング）
        best_match = None
        min_time_diff = float('inf')
        
        for hyp_ts, hyp_text in hyp_data:
            # タイムスタンプの差を計算（秒単位）
            ref_seconds = sum(int(x) * 60 ** (2-i) for i, x in enumerate(ref_ts.split(':')))
            hyp_seconds = sum(int(x) * 60 ** (2-i) for i, x in enumerate(hyp_ts.split(':')))
            time_diff = abs(ref_seconds - hyp_seconds)
            
            if time_diff < min_time_diff:
                min_time_diff = time_diff
                best_match = (hyp_ts, hyp_text)
        
        if best_match and min_time_diff <= 10:  # 10秒以内の誤差なら対応
            hyp_ts, hyp_text = best_match
            wer = calculate_wer(ref_text, hyp_text)
            total_wer += wer
            matched_pairs += 1
            
            if verbose or wer > 0.3:  # 詳細表示または高エラー率
                print(f"\n[{ref_ts}] 発話 {i+1}")
                print(f"正解: {ref_text}")
                print(f"認識: {hyp_text}")
                print(f"WER: {wer:.3f} ({'✅' if wer < 0.1 else '⚠️' if wer < 0.3 else '❌'})")
                
                if verbose:
                    # 詳細差分表示
                    diff = list(difflib.unified_diff(
                        [ref_text], [hyp_text], 
                        fromfile='正解', tofile='認識', lineterm=''
                    ))
                    if len(diff) > 2:
                        for line in diff[2:]:
                            print(f"  {line}")
        else:
            print(f"\n[{ref_ts}] 発話 {i+1} - ❌ 対応する認識結果なし")
            print(f"正解: {ref_text}")
    
    # 統計表示
    print("\n" + "=" * 60)
    if matched_pairs > 0:
        avg_wer = total_wer / matched_pairs
        accuracy = (1 - avg_wer) * 100
        print(f"📈 評価結果:")
        print(f"  マッチした発話: {matched_pairs}/{len(ref_data)}")
        print(f"  平均WER: {avg_wer:.3f}")
        print(f"  認識精度: {accuracy:.1f}%")
        
        # 評価判定
        if accuracy >= 95:
            print(f"  判定: ✅ 優秀")
        elif accuracy >= 90:
            print(f"  判定: 🟢 良好")
        elif accuracy >= 80:
            print(f"  判定: 🟡 普通")
        else:
            print(f"  判定: 🔴 要改善")
    else:
        print("❌ マッチする発話がありませんでした")

def main():
    parser = argparse.ArgumentParser(description="音声認識精度評価")
    parser.add_argument('reference', help='正解データファイル')
    parser.add_argument('hypothesis', help='音声認識結果ファイル')
    parser.add_argument('--verbose', '-v', action='store_true', help='詳細表示')
    
    args = parser.parse_args()
    
    if not Path(args.reference).exists():
        print(f"❌ 正解データファイルが見つかりません: {args.reference}")
        return
    
    if not Path(args.hypothesis).exists():
        print(f"❌ 音声認識結果ファイルが見つかりません: {args.hypothesis}")
        return
    
    compare_transcriptions(args.reference, args.hypothesis, args.verbose)

if __name__ == "__main__":
    main() 