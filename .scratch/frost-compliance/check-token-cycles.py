#!/usr/bin/env python3
"""Frost token 静态检查：自引用与循环自定义属性会让 token 计算为 invalid（guaranteed-invalid value）。
用法：python3 .scratch/frost-compliance/check-token-cycles.py  （在 frontend/ 上层仓库根运行）"""
import re, sys, glob, os

ROOT = os.path.join(os.path.dirname(__file__), '..', '..', 'frontend')
files = [os.path.join(ROOT,'app','globals.css'), os.path.join(ROOT,'app','frost-materials.css')] \
        + glob.glob(os.path.join(ROOT,'app','*','styles.css'))

DECL = re.compile(r'^\s*(--[a-z0-9-]+)\s*:\s*([^;]+);', re.M)
VARS = re.compile(r'var\(\s*(--[a-z0-9-]+)')

problems = []
for f in files:
    if not os.path.exists(f): continue
    txt = open(f, encoding='utf-8').read()
    edges = {}          # name -> set(referenced names)，同名多次声明取并集
    where = {}
    for m in DECL.finditer(txt):
        name, val = m.group(1), m.group(2)
        line = txt[:m.start()].count('\n') + 1
        refs = set(VARS.findall(val))
        edges.setdefault(name, set()).update(refs)
        where.setdefault(name, line)
        if name in refs:
            problems.append(f'{f}:{line}  自引用  {name}: {val.strip()}')
    # 环检测（DFS）
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {}
    def dfs(n, stack):
        color[n] = GRAY
        for m2 in edges.get(n, ()):
            if m2 not in edges:      # 引用了别处/未声明的名字，不构成本文件内的环
                continue
            c = color.get(m2, WHITE)
            if c == GRAY:
                cyc = ' → '.join(stack[stack.index(m2):] + [m2]) if m2 in stack else f'{n} → {m2}'
                problems.append(f'{f}:{where.get(m2, "?")}  循环引用  {cyc}')
            elif c == WHITE:
                dfs(m2, stack + [m2])
        color[n] = BLACK
    for n in list(edges):
        if color.get(n, WHITE) == WHITE:
            dfs(n, [n])

if problems:
    print('发现自引用 / 循环自定义属性（会令 token 计算为 invalid）：')
    for p in sorted(set(problems)): print('  ' + p)
    sys.exit(1)
print('OK：无自引用、无循环自定义属性。')
