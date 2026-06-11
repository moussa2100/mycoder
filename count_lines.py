import os

base = 'pgimcode'
dirs_to_scan = [
    'pgimcode',
    'pgimcode/agents',
    'pgimcode/tools',
    'pgimcode/discovery',
    'pgimcode/memory',
]

for d in dirs_to_scan:
    for fname in sorted(os.listdir(d)):
        if fname.endswith('.py'):
            fp = os.path.join(d, fname)
            try:
                with open(fp, encoding='utf-8') as fh:
                    n = sum(1 for _ in fh)
                print(f'{n:>5d} {fp}')
            except Exception as e:
                print(f'  ERR {fp}: {e}')
