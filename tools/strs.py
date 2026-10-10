import sys,re
# usage: strs.py <file> <base-hex> <regex> [minlen]
d=open(sys.argv[1],'rb').read()
base=int(sys.argv[2],16)
kw=re.compile(sys.argv[3],re.I)
mn=int(sys.argv[4]) if len(sys.argv)>4 else 3
for m in re.finditer(rb'[\x20-\x7e]{%d,}'%mn,d):
    t=m.group().decode()
    if kw.search(t): print(f'{base+m.start():#010x}: {t[:120]}')
