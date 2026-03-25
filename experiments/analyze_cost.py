import json

total_in = 0
total_out = 0
rows = 0
call_counts = {}

with open('results/raw/batch_eval50_stageC_v10.5_20260320_171704.jsonl', 'r') as f:
    for line in f:
        rows += 1
        data = json.loads(line)
        if 'token_log' in data:
            for call in data['token_log']:
                total_in += call.get('input', 0)
                total_out += call.get('output', 0)
                call_name = call.get('call', 'unknown')
                if call_name not in call_counts:
                    call_counts[call_name] = {'count': 0, 'in': 0, 'out': 0}
                call_counts[call_name]['count'] += 1
                call_counts[call_name]['in'] += call.get('input', 0)
                call_counts[call_name]['out'] += call.get('output', 0)

print(f'Rows: {rows}')
print(f'Total input tokens:  {total_in:,}')
print(f'Total output tokens: {total_out:,}')
print()
print('Cost (0.5 USD/1M input, 3 USD/1M output):')
input_cost = total_in * 0.5 / 1e6
output_cost = total_out * 3 / 1e6
total_cost = input_cost + output_cost
print(f'  Input:  ${input_cost:.4f}')
print(f'  Output: ${output_cost:.4f}')
print(f'  TOTAL:  ${total_cost:.4f}')
print()
if call_counts:
    print('Top calls by tokens:')
    sorted_calls = sorted(call_counts.keys(), key=lambda x: call_counts[x]['in'] + call_counts[x]['out'], reverse=True)
    for name in sorted_calls[:15]:
        info = call_counts[name]
        cost = (info['in'] * 0.5 + info['out'] * 3) / 1e6
        print(f'  {name:35s}  {info["count"]:2d} x  in={info["in"]:7,}  out={info["out"]:7,}  ${cost:.4f}')
