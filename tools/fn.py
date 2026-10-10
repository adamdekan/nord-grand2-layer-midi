import sys,re
# usage: fn.py <decomp.c> show <addr|name> ...   -> print function bodies
#        fn.py <decomp.c> callers <name>           -> functions whose body mentions name
#        fn.py <decomp.c> grep <regex>              -> function names + matching lines
src=open(sys.argv[1],encoding='utf-8',errors='replace').read()
parts=re.split(r'(?m)^//==== ',src)[1:]
funcs={}
for p in parts:
    hdr,_,body=p.partition('\n'); name,_,addr=hdr.partition(' @ ')
    funcs[addr.strip().lower()]=(name.strip(),body)
cmd=sys.argv[2]
if cmd=='show':
    for a in sys.argv[3:]:
        a=a.lower().replace('fun_','').replace('0x','')
        for k,(n,b) in funcs.items():
            if k==a or n.lower()==a:
                print(f'//==== {n} @ {k}\n{b}')
elif cmd=='callers':
    pat=re.compile(re.escape(sys.argv[3])+r'\b')
    for k,(n,b) in funcs.items():
        if n!=sys.argv[3] and pat.search(b):
            print(k,n)
elif cmd=='grep':
    pat=re.compile(sys.argv[3])
    for k,(n,b) in funcs.items():
        hits=[l.strip() for l in b.split('\n') if pat.search(l)]
        if hits: print(f'{k} {n}: '+' || '.join(hits[:4])[:300])
