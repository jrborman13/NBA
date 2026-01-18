#!/usr/bin/env python3
"""
Performance analysis script for prediction generation.
Analyzes timing data from debug.log to identify bottlenecks.
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

def analyze_performance_logs(log_path):
    """Analyze performance logs and generate a summary report."""
    
    log_file = Path(log_path)
    if not log_file.exists():
        print(f"Log file not found: {log_path}")
        return
    
    perf_data = {
        'bulk_fetches': [],
        'player_predictions': [],
        'feature_gathering': [],
        'prediction_generation': [],
        'totals': []
    }
    
    with open(log_file, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                if entry.get('runId') != 'perf-analysis' or entry.get('hypothesisId') != 'PERF':
                    continue
                
                message = entry.get('message', '')
                data = entry.get('data', {})
                
                if 'Bulk data fetch completed' in message:
                    perf_data['bulk_fetches'].append({
                        'timestamp': entry.get('timestamp', 0),
                        'bulk_game_logs_ms': data.get('bulk_game_logs_ms', 0),
                        'bulk_advanced_ms': data.get('bulk_advanced_ms', 0),
                        'bulk_drives_ms': data.get('bulk_drives_ms', 0),
                        'bulk_synergy_ms': data.get('bulk_synergy_ms', 0),
                        'bulk_total_ms': data.get('bulk_total_ms', 0)
                    })
                
                elif 'Player prediction completed' in message:
                    perf_data['player_predictions'].append({
                        'timestamp': entry.get('timestamp', 0),
                        'player_id': data.get('player_id', ''),
                        'player_name': data.get('player_name', ''),
                        'prediction_time_ms': data.get('prediction_time_ms', 0),
                        'player_total_time_ms': data.get('player_total_time_ms', 0),
                        'player_index': data.get('player_index', 0),
                        'total_players': data.get('total_players', 0)
                    })
                
                elif 'Feature gathering completed' in message:
                    perf_data['feature_gathering'].append({
                        'timestamp': entry.get('timestamp', 0),
                        'player_id': data.get('player_id', ''),
                        'features_total_time_ms': data.get('features_total_time_ms', 0),
                        'logs_time_ms': data.get('logs_time_ms', 0),
                        'rolling_time_ms': data.get('rolling_time_ms', 0)
                    })
                
                elif 'Prediction generation completed' in message:
                    perf_data['prediction_generation'].append({
                        'timestamp': entry.get('timestamp', 0),
                        'predict_total_time_ms': data.get('predict_total_time_ms', 0),
                        'stat_times_ms': data.get('stat_times_ms', {})
                    })
                
                elif 'All predictions completed' in message:
                    perf_data['totals'].append({
                        'timestamp': entry.get('timestamp', 0),
                        'total_time_ms': data.get('total_time_ms', 0),
                        'bulk_fetch_time_ms': data.get('bulk_fetch_time_ms', 0),
                        'avg_player_time_ms': data.get('avg_player_time_ms', 0),
                        'total_players': data.get('total_players', 0),
                        'successful_players': data.get('successful_players', 0)
                    })
                
            except json.JSONDecodeError:
                continue
    
    # Generate report
    print("=" * 80)
    print("PREDICTION GENERATION PERFORMANCE ANALYSIS")
    print("=" * 80)
    print()
    
    if perf_data['totals']:
        total = perf_data['totals'][0]
        print(f"Total Players: {total['total_players']}")
        print(f"Successful Players: {total['successful_players']}")
        print(f"Total Time: {total['total_time_ms']:.1f} ms ({total['total_time_ms']/1000:.2f} seconds)")
        print(f"Average Time Per Player: {total['avg_player_time_ms']:.1f} ms")
        print()
    
    if perf_data['bulk_fetches']:
        bulk = perf_data['bulk_fetches'][0]
        print("BULK DATA FETCH TIMING:")
        print(f"  Game Logs: {bulk['bulk_game_logs_ms']:.1f} ms")
        print(f"  Advanced Stats: {bulk['bulk_advanced_ms']:.1f} ms")
        print(f"  Drives Stats: {bulk['bulk_drives_ms']:.1f} ms")
        print(f"  Offensive Synergy: {bulk['bulk_synergy_ms']:.1f} ms")
        print(f"  Total Bulk Fetch: {bulk['bulk_total_ms']:.1f} ms ({bulk['bulk_total_ms']/1000:.2f} seconds)")
        print()
    
    if perf_data['player_predictions']:
        player_times = [p['player_total_time_ms'] for p in perf_data['player_predictions']]
        pred_times = [p['prediction_time_ms'] for p in perf_data['player_predictions']]
        
        print("PER-PLAYER TIMING STATISTICS:")
        print(f"  Average Total Time: {sum(player_times)/len(player_times):.1f} ms")
        print(f"  Min Total Time: {min(player_times):.1f} ms")
        print(f"  Max Total Time: {max(player_times):.1f} ms")
        print(f"  Average Prediction Time: {sum(pred_times)/len(pred_times):.1f} ms")
        print()
        
        # Find slowest players
        slowest = sorted(perf_data['player_predictions'], key=lambda x: x['player_total_time_ms'], reverse=True)[:5]
        print("SLOWEST 5 PLAYERS:")
        for p in slowest:
            print(f"  {p['player_name']}: {p['player_total_time_ms']:.1f} ms (prediction: {p['prediction_time_ms']:.1f} ms)")
        print()
    
    if perf_data['feature_gathering']:
        feature_times = [f['features_total_time_ms'] for f in perf_data['feature_gathering']]
        logs_times = [f['logs_time_ms'] for f in perf_data['feature_gathering']]
        rolling_times = [f['rolling_time_ms'] for f in perf_data['feature_gathering']]
        
        print("FEATURE GATHERING STATISTICS:")
        print(f"  Average Total Time: {sum(feature_times)/len(feature_times):.1f} ms")
        print(f"  Average Logs Extraction: {sum(logs_times)/len(logs_times):.1f} ms")
        print(f"  Average Rolling Averages: {sum(rolling_times)/len(rolling_times):.1f} ms")
        print()
    
    if perf_data['prediction_generation']:
        pred_gen_times = [p['predict_total_time_ms'] for p in perf_data['prediction_generation']]
        stat_times_agg = defaultdict(list)
        
        for p in perf_data['prediction_generation']:
            for stat, time_ms in p.get('stat_times_ms', {}).items():
                stat_times_agg[stat].append(time_ms)
        
        print("PREDICTION GENERATION STATISTICS:")
        print(f"  Average Total Time: {sum(pred_gen_times)/len(pred_gen_times):.1f} ms")
        print()
        print("  Average Time Per Stat:")
        for stat in sorted(stat_times_agg.keys()):
            avg_time = sum(stat_times_agg[stat]) / len(stat_times_agg[stat])
            print(f"    {stat}: {avg_time:.1f} ms")
        print()
    
    # Calculate breakdown
    if perf_data['totals'] and perf_data['bulk_fetches']:
        total = perf_data['totals'][0]
        bulk = perf_data['bulk_fetches'][0]
        per_player_time = total['total_time_ms'] - bulk['bulk_total_ms']
        per_player_avg = per_player_time / total['total_players'] if total['total_players'] > 0 else 0
        
        print("TIME BREAKDOWN:")
        print(f"  Bulk Data Fetch: {bulk['bulk_total_ms']:.1f} ms ({bulk['bulk_total_ms']/total['total_time_ms']*100:.1f}%)")
        print(f"  Per-Player Processing: {per_player_time:.1f} ms ({per_player_time/total['total_time_ms']*100:.1f}%)")
        print(f"  Average Per Player: {per_player_avg:.1f} ms")
        print()

if __name__ == '__main__':
    log_path = sys.argv[1] if len(sys.argv) > 1 else '/Users/jackborman/Desktop/PycharmProjects/NBA/.cursor/debug.log'
    analyze_performance_logs(log_path)
