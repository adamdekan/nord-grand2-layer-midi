import sys,collections
# usage: lzostat.py <packed>...  -> histogram of LZO1X instruction kinds used in a stream
def stat(src):
    c=collections.Counter(); ip=0; state=0; outlen=0; maxd=collections.Counter()
    t=src[ip]
    if t>17:
        ip+=1; t-=17; ip+=t; outlen+=t; state=4 if t>=4 else t; c['init_lit']+=1
    while True:
        t=src[ip]; ip+=1
        if t<16:
            if state==0:
                if t==0:
                    while src[ip]==0: t+=255; ip+=1
                    t+=15+src[ip]; ip+=1; c['lit_ext']+=1
                else: c['lit']+=1
                ip+=t+3; outlen+=t+3; state=4; continue
            if state==4: ln=3; c['M1_after_lit(len3,+0x800)']+=1
            else: ln=2; c['M1_after_match(len2)']+=1
            ip+=1; tr=t&3
        elif t>=64:
            ip+=1; ln=(t>>5)+1; tr=t&3; c['M2']+=1
        elif t>=32:
            t&=31
            if t==0:
                while src[ip]==0: t+=255; ip+=1
                t+=31+src[ip]; ip+=1; c['M3_ext']+=1
            else: c['M3']+=1
            ln=t+2; tr=src[ip]&3; ip+=2
        else:
            h=(t&8)<<11; t&=7
            if t==0:
                while src[ip]==0: t+=255; ip+=1
                t+=7+src[ip]; ip+=1
            ln=t+2; d=(src[ip]>>2)|(src[ip+1]<<6); tr=src[ip]&3; ip+=2
            if h+d==0: c['END']+=1; return c,ip
            c['M4']+=1
        outlen+=ln+tr; ip+=tr; state=tr
        c['trail%d'%tr]+=1
for f in sys.argv[1:]:
    c,used=stat(open(f,'rb').read())
    print(f, used); [print('  %-28s %d'%(k,v)) for k,v in sorted(c.items())]
