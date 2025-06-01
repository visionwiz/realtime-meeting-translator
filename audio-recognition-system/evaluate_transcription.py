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

def normalize_timestamp_to_seconds(timestamp_str: str, base_time: int = 0) -> int:
    """タイムスタンプを秒に正規化（異なる形式対応）"""
    parts = timestamp_str.split(':')
    if len(parts) == 3:
        hours, minutes, seconds = map(int, parts)
        total_seconds = hours * 3600 + minutes * 60 + seconds
        
        # 音声ファイル内経過時間形式の場合（00:xx:xx）
        if hours == 0 and minutes < 10:
            return total_seconds
        
        # 実際の時刻形式の場合（HH:MM:SS）- base_timeからの経過時間を計算
        if base_time > 0:
            return total_seconds - base_time
        
        return total_seconds
    return 0

def estimate_audio_start_time(hyp_data: List[Tuple[str, str]]) -> int:
    """音声ファイル開始時刻を推定（認識結果の最初のタイムスタンプから）"""
    if not hyp_data:
        return 0
    
    first_timestamp = hyp_data[0][0]
    parts = first_timestamp.split(':')
    if len(parts) == 3:
        hours, minutes, seconds = map(int, parts)
        # 実際の時刻形式かチェック（時間が1以上または分が10以上）
        if hours > 0 or minutes >= 10:
            return hours * 3600 + minutes * 60 + seconds
    
    return 0

def text_similarity(text1: str, text2: str) -> float:
    """テキスト類似度を計算（0-1の範囲）"""
    # 文字単位の類似度を計算
    matcher = difflib.SequenceMatcher(None, text1, text2)
    return matcher.ratio()

def find_optimal_matches(ref_data_sorted: List, hyp_data_sorted: List, time_threshold: int = 45) -> List[Tuple]:
    """最適なマッチングを見つける（テキスト類似度重視）"""
    matches = []
    used_hyp_indices = set()
    
    for i, (ref_seconds, ref_ts, ref_text) in enumerate(ref_data_sorted):
        best_match = None
        best_text_sim = -1
        best_hyp_index = -1
        
        for j, (hyp_seconds, hyp_ts, hyp_text) in enumerate(hyp_data_sorted):
            if j in used_hyp_indices:
                continue
            
            # 時間差（参考のみ - 大幅なずれは除外）
            time_diff = abs(ref_seconds - hyp_seconds)
            if time_diff > time_threshold:  # 45秒以上のずれは除外
                continue
            
            # テキスト類似度（主要指標）
            text_sim = text_similarity(ref_text, hyp_text)
            
            # 長文の場合の部分マッチングも考慮
            partial_sim = 0
            if len(ref_text) > 30 or len(hyp_text) > 30:  # 長文の場合
                # 部分的な一致もチェック
                ref_words = ref_text.split()
                hyp_words = hyp_text.split()
                common_words = set(ref_words) & set(hyp_words)
                if ref_words and hyp_words:
                    partial_sim = len(common_words) / max(len(ref_words), len(hyp_words))
                text_sim = max(text_sim, partial_sim * 0.8)  # 部分マッチは80%掛け
            
            # 最高のテキスト類似度を持つマッチを選択
            if text_sim > best_text_sim:
                best_text_sim = text_sim
                best_match = (hyp_seconds, hyp_ts, hyp_text, time_diff, text_sim)
                best_hyp_index = j
        
        # マッチング判定: テキスト類似度のみ
        # 類似度0.3以上でマッチ
        min_threshold = 0.3
        
        if best_match and best_text_sim >= min_threshold:
            matches.append((
                i, ref_seconds, ref_ts, ref_text,
                best_hyp_index, best_match[0], best_match[1], best_match[2],
                best_match[3], best_match[4]  # combined_score削除
            ))
            used_hyp_indices.add(best_hyp_index)
        else:
            # マッチなし
            matches.append((
                i, ref_seconds, ref_ts, ref_text,
                -1, -1, "", "", -1, -1  # combined_score削除
            ))
    
    return matches

def compare_transcriptions(reference_file: str, hypothesis_file: str, verbose: bool = False):
    """音声認識結果と正解データを比較（テキスト認識精度重視版）"""
    print(f"📊 音声認識精度評価（テキスト認識精度重視）")
    print(f"正解データ: {reference_file}")
    print(f"認識結果: {hypothesis_file}")
    print("=" * 60)
    
    # ファイル読み込み
    ref_data = parse_transcript_file(reference_file)
    hyp_data = parse_transcript_file(hypothesis_file)
    
    print(f"正解データ発話数: {len(ref_data)}")
    print(f"認識結果発話数: {len(hyp_data)}")
    
    # 音声ファイル開始時刻を推定
    base_time = estimate_audio_start_time(hyp_data)
    if base_time > 0:
        base_hours = base_time // 3600
        base_minutes = (base_time % 3600) // 60
        base_seconds = base_time % 60
        print(f"推定音声開始時刻: {base_hours:02d}:{base_minutes:02d}:{base_seconds:02d}")
    else:
        print("タイムスタンプ形式: 音声ファイル内経過時間")
    
    print("-" * 60)
    
    # データを時系列順にソート
    hyp_data_sorted = []
    for hyp_ts, hyp_text in hyp_data:
        hyp_seconds = normalize_timestamp_to_seconds(hyp_ts, base_time)
        hyp_data_sorted.append((hyp_seconds, hyp_ts, hyp_text))
    hyp_data_sorted.sort(key=lambda x: x[0])
    
    ref_data_sorted = []
    for ref_ts, ref_text in ref_data:
        ref_seconds = normalize_timestamp_to_seconds(ref_ts)
        ref_data_sorted.append((ref_seconds, ref_ts, ref_text))
    ref_data_sorted.sort(key=lambda x: x[0])
    
    # デバッグ情報
    if verbose:
        print("\n🔍 デバッグ情報:")
        print("正解データタイムライン:")
        for ref_seconds, ref_ts, ref_text in ref_data_sorted:
            print(f"  {ref_seconds:3d}秒 [{ref_ts}] {ref_text[:50]}...")
        print("\n認識結果タイムライン:")
        for hyp_seconds, hyp_ts, hyp_text in hyp_data_sorted:
            print(f"  {hyp_seconds:3d}秒 [{hyp_ts}] {hyp_text[:50]}...")
        print("")
    
    # 最適マッチングを実行（テキスト類似度重視）
    matches = find_optimal_matches(ref_data_sorted, hyp_data_sorted, time_threshold=45)
    
    # 結果を表示
    total_wer = 0
    matched_pairs = 0
    
    for match in matches:
        (ref_idx, ref_seconds, ref_ts, ref_text,
         hyp_idx, hyp_seconds, hyp_ts, hyp_text,
         time_diff, text_sim) = match  # combined_score削除
        
        if hyp_idx >= 0:  # マッチした場合
            wer = calculate_wer(ref_text, hyp_text)
            total_wer += wer
            matched_pairs += 1
            
            if verbose or wer > 0.3:  # 詳細表示または高エラー率
                print(f"\n[{ref_ts}] 発話 {ref_idx+1} → [{hyp_ts}]")
                print(f"正解: {ref_text}")
                print(f"認識: {hyp_text}")
                print(f"WER: {wer:.3f} | 類似度: {text_sim:.3f} ({'✅' if wer < 0.1 else '⚠️' if wer < 0.3 else '❌'})")
                if verbose and abs(time_diff) > 10:
                    print(f"参考: 時差 {time_diff:.0f}秒")
                
                if verbose:
                    # 詳細差分表示
                    diff = list(difflib.unified_diff(
                        [ref_text], [hyp_text], 
                        fromfile='正解', tofile='認識', lineterm=''
                    ))
                    if len(diff) > 2:
                        for line in diff[2:]:
                            print(f"  {line}")
            elif wer < 0.3:  # 良好な結果は簡潔に表示
                print(f"\n[{ref_ts}] 発話 {ref_idx+1} → [{hyp_ts}] ✅ WER: {wer:.3f} | 類似度: {text_sim:.3f}")
        else:  # マッチしなかった場合
            print(f"\n[{ref_ts}] 発話 {ref_idx+1} - ❌ 対応する認識結果なし")
            print(f"正解: {ref_text}")
    
    # 使用されなかった認識結果をチェック
    used_hyp_indices = {match[4] for match in matches if match[4] >= 0}
    unused_hyp = []
    for j, (hyp_seconds, hyp_ts, hyp_text) in enumerate(hyp_data_sorted):
        if j not in used_hyp_indices:
            unused_hyp.append((hyp_ts, hyp_text))
    
    if unused_hyp and verbose:
        print(f"\n📋 マッチしなかった認識結果 ({len(unused_hyp)}件):")
        for hyp_ts, hyp_text in unused_hyp:
            print(f"  [{hyp_ts}] {hyp_text}")
    
    # 統計表示
    print("\n" + "=" * 60)
    if matched_pairs > 0:
        avg_wer = total_wer / matched_pairs
        accuracy = max(0, (1 - avg_wer) * 100)  # 負の値を防ぐ
        match_rate = (matched_pairs / len(ref_data)) * 100
        
        print(f"📈 音声認識精度評価結果:")
        print(f"  マッチした発話: {matched_pairs}/{len(ref_data)} ({match_rate:.1f}%)")
        print(f"  平均WER: {avg_wer:.3f}")
        print(f"  音声認識精度: {accuracy:.1f}%")
        
        # 評価判定（テキスト認識精度重視）
        if match_rate >= 90 and accuracy >= 95:
            print(f"  総合判定: ✅ 優秀 - 高精度な音声認識")
        elif match_rate >= 80 and accuracy >= 90:
            print(f"  総合判定: 🟢 良好 - 実用的な音声認識")
        elif match_rate >= 70 and accuracy >= 80:
            print(f"  総合判定: 🟡 普通 - 改善の余地あり")
        else:
            print(f"  総合判定: 🔴 要改善 - 音声認識精度に課題")
            
        # 改善提案（テキスト認識重視）
        if match_rate < 80:
            print(f"\n💡 改善提案:")
            print(f"  - マッチ率が低いです。音声ファイルと正解データの内容を確認してください")
            print(f"  - 類似した発話が複数ある場合、正解データの粒度を調整してください")
        elif accuracy < 80:
            print(f"\n💡 改善提案:")
            print(f"  - 音声認識精度が低いです。以下を確認してください:")
            print(f"    • 音声品質（雑音、音量、明瞭さ）")
            print(f"    • マイクの設定や環境音の除去")
            print(f"    • 音声認識モデルの選択")
    else:
        print("❌ マッチする発話がありませんでした")
        print("\n💡 改善提案:")
        print("  - 正解データと認識結果の内容が大きく異なる可能性があります")
        print("  - 音声ファイルと正解データの対応を確認してください")
        print("  - --verbose オプションで詳細な差分を確認してください")

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