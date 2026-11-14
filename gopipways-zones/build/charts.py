"""Synthetic (illustrative) candlestick scenarios for the Gopipways zones video.
Each scenario -> {symbol, candles[[o,h,l,c]], ymin,ymax, beats{scene:{upto,title,sub,chip}}, ann[...]}"""
import random
def build(start,legs,seed):
    rng=random.Random(seed);C=[];M={};prev=start
    for leg in legs:
        name,target,n,vol=leg[:4];opt=leg[4] if len(leg)>4 else {}
        p0=prev
        for j in range(1,n+1):
            base=p0+(target-p0)*j/n
            c=target if j==n else base+rng.gauss(0,vol)
            o=prev;wv=vol*0.7
            hi=max(o,c)+abs(rng.gauss(0,wv));lo=min(o,c)-abs(rng.gauss(0,wv))
            if j==n:
                if 'tap_hi' in opt:hi=opt['tap_hi']
                if 'tap_lo' in opt:lo=opt['tap_lo']
            if 'cap' in opt:hi=min(hi,opt['cap'])
            if 'floor' in opt:lo=max(lo,opt['floor'])
            C.append([round(o,2),round(hi,2),round(lo,2),round(c,2)]);prev=c
        M[name]=len(C)-1
    return C,M
S={}
def scen(id,symbol,start,legs,seed,beats,ann,pad=30):
    C,M=build(start,legs,seed)
    def ix(v):return M[v] if isinstance(v,str) else v
    b={}
    for k,d in beats.items():
        d=dict(d);d['upto']=ix(d['upto'])+1;b[k]=d
    A=[]
    for a in ann:
        a=dict(a)
        for key in('idx','from','to','at'):
            if key in a:a[key]=ix(a[key])
        A.append(a)
    prices=[x for c in C for x in c[1:3]]
    for a in A:
        for key in('price','entry','stop','target','p1','p2'):
            if key in a:prices.append(a[key])
    S[id]=dict(symbol=symbol,candles=C,ymin=min(prices)-pad,ymax=max(prices)+pad,beats=b,ann=A,markers=M)
SYM="GOLD / 1H / ILLUSTRATION"
T,G,Rd='#2db3a6','#e6b85c','#e24163'
# ---- A: resistance, 3 rejections (scenes 7,8)
scen('A',SYM,4380,[('r1',4496,10,6,{'tap_hi':4500}),('d1',4430,6,6),('r2',4497,7,6,{'tap_hi':4500}),('d2',4420,7,6),('r3',4498,8,6,{'tap_hi':4500}),('d3',4370,8,6)],11,
 {7:dict(upto='d1',title='WHAT IS RESISTANCE?',sub='Price rises, meets selling pressure, then falls.',chip='BASICS / RESISTANCE'),
  8:dict(upto='d3',title='REJECTED THREE TIMES',sub='Each touch of the level was rejected.',chip='BASICS / RESISTANCE')},
 [dict(type='hline',price=4500,label='RESISTANCE',color=G,idx=0,scene=7),
  dict(type='arrow',idx='r1',price=4500,dir='down',color=Rd,text='1',scene=8),dict(type='arrow',idx='r2',price=4500,dir='down',color=Rd,text='2',scene=8),dict(type='arrow',idx='r3',price=4500,dir='down',color=Rd,text='3',scene=8)])
# ---- B: support, bounces (scene 9)
scen('B',SYM,4220,[('s1',4104,10,6,{'tap_lo':4100}),('u1',4180,6,6),('s2',4103,7,6,{'tap_lo':4100}),('u2',4190,7,6),('s3',4102,8,6,{'tap_lo':4100}),('u3',4240,8,6)],21,
 {9:dict(upto='u3',title='WHAT IS SUPPORT?',sub='Price falls to a level, then buyers step in.',chip='BASICS / SUPPORT')},
 [dict(type='hline',price=4100,label='SUPPORT',color=T,idx=0),
  dict(type='arrow',idx='s1',price=4100,dir='up',color=T,text='1'),dict(type='arrow',idx='s2',price=4100,dir='up',color=T,text='2'),dict(type='arrow',idx='s3',price=4100,dir='up',color=T,text='3')])
# ---- C: level respected (scene 12)
scen('C',SYM,4300,[('t1',4212,9,6,{'tap_lo':4200}),('b1',4290,6,6),('t2',4210,7,6,{'tap_lo':4200}),('b2',4285,6,6),('t3',4208,7,6,{'tap_lo':4200}),('b3',4280,6,6),('t4',4214,6,6,{'tap_lo':4201})],31,
 {12:dict(upto='t4',title='SPOTTING A LEVEL',sub='A price area that price respected more than once.',chip='BASICS / SPOT THE LEVEL')},
 [dict(type='zone',p1=4200,p2=4215,label='RESPECTED ZONE',color=G,idx=0),
  dict(type='tag',idx='t1',price=4200,text='1',dy=38,color=T),dict(type='tag',idx='t2',price=4200,text='2',dy=38,color=T),dict(type='tag',idx='t3',price=4200,text='3',dy=38,color=T),dict(type='tag',idx='t4',price=4200,text='4TH TEST?',dy=44,color=G)])
# ---- D: breakout, no guarantee (scene 14)
scen('D',SYM,4380,[('r1',4497,8,6,{'tap_hi':4500}),('d1',4440,5,6),('r2',4496,6,6,{'tap_hi':4500}),('d2',4430,5,6),('r3',4498,6,6,{'tap_hi':4500}),('d3',4450,4,6),('brk',4565,6,5),('run',4630,7,5)],41,
 {14:dict(upto='run',title='NO GUARANTEE ON THE 4TH TEST',sub='Price can break through and keep going.',chip='BASICS / RESISTANCE CAN BREAK')},
 [dict(type='hline',price=4500,label='RESISTANCE',color=G,idx=0),
  dict(type='arrow',idx='r1',price=4500,dir='down',color=Rd,text=''),dict(type='arrow',idx='r2',price=4500,dir='down',color=Rd,text=''),dict(type='arrow',idx='r3',price=4500,dir='down',color=Rd,text=''),
  dict(type='tag',idx='brk',price=4565,text='4TH TEST: BREAKS HIGHER',dy=-46,color=T)])
# ---- E: support flips to resistance (scene 16)
scen('E',SYM,4200,[('s1',4104,7,6,{'tap_lo':4100}),('u1',4170,5,6),('s2',4103,6,6,{'tap_lo':4100}),('u2',4180,5,6),('brk',4040,7,5),('pull',4098,6,5,{'tap_hi':4106}),('dn',4010,9,5)],51,
 {16:dict(upto='dn',title='SUPPORT BECOMES RESISTANCE',sub='A broken support can reject price on the way back.',chip='ROLE REVERSAL / 01')},
 [dict(type='hline',price=4100,label='SUPPORT',color=T,idx=0,to='u2'),
  dict(type='hline',price=4100,label='NOW RESISTANCE',color=Rd,idx='brk'),
  dict(type='arrow',idx='pull',price=4106,dir='down',color=Rd,text='REJECTED')])
# ---- F: resistance flips to support (scene 17)
scen('F',SYM,4060,[('r1',4146,8,5,{'tap_hi':4150}),('d1',4100,4,5),('r2',4147,6,5,{'tap_hi':4150}),('d2',4095,4,5),('brk',4215,6,5),('pb',4152,6,5,{'tap_lo':4148}),('up',4230,8,5)],61,
 {17:dict(upto='up',title='RESISTANCE BECOMES SUPPORT',sub='Price returns to the old level and buyers defend it.',chip='ROLE REVERSAL / 02')},
 [dict(type='hline',price=4150,label='RESISTANCE',color=Rd,idx=0,to='d2'),
  dict(type='hline',price=4150,label='NOW SUPPORT',color=T,idx='brk'),
  dict(type='arrow',idx='pb',price=4148,dir='up',color=T,text='DEFENDED')])
# ---- F2: support flips again, second example (scene 18)
scen('F2',SYM,4380,[('s1',4306,7,5,{'tap_lo':4300}),('u1',4360,5,5),('s2',4305,6,5,{'tap_lo':4300}),('u2',4365,5,5),('brk',4250,7,5),('pull',4298,6,5,{'tap_hi':4308}),('dn',4200,9,5)],71,
 {18:dict(upto='dn',title='THE OPPOSITE EXAMPLE',sub='Support held twice, broke, then met resistance.',chip='ROLE REVERSAL / 03')},
 [dict(type='hline',price=4300,label='SUPPORT',color=T,idx=0,to='u2'),
  dict(type='hline',price=4300,label='NOW RESISTANCE',color=Rd,idx='brk'),
  dict(type='arrow',idx='pull',price=4308,dir='down',color=Rd,text='REJECTED')])
# ---- H: support example, strength + structure (scenes 37,42,44-51)
H=dict(zone=(4290,4310))
scen('H',SYM,4400,[('a1',4332,8,5),('t1',4302,5,4,{'tap_lo':4292}),('u1',4380,6,5),('d1',4338,5,5),('t2',4304,5,4,{'tap_lo':4291}),('u2s',4332,2,3),
  ('imp',4470,6,4),('pb',4318,10,5),('ent',4322,1,2,{'tap_lo':4296}),('r1',4400,8,5),('p1',4350,5,5),('t3',4322,3,4,{'tap_lo':4294}),('big',4560,12,5)],81,
 {37:dict(upto='u2s',title='A POTENTIAL SUPPORT',sub='Two touches. Is that enough?',chip='ZONE CHECK / THE EXAMPLE'),
  42:dict(upto='imp',title='QUESTION 1: STRENGTH',sub='Did price leave the zone with a strong move?',chip='01 / STRONG REACTION'),
  44:dict(upto='imp',title='QUESTION 2: STRUCTURE',sub='Did price take out a previous significant high?',chip='02 / BREAK OF STRUCTURE'),
  45:dict(upto='imp',title='BULLISH BREAK OF STRUCTURE',sub='A fresh higher high above the previous high.',chip='02 / BREAK OF STRUCTURE'),
  46:dict(upto='imp',title='WEAK BOUNCE vs STRONG MOVE',sub='A small bounce that falls back is not the same signal.',chip='02 / BREAK OF STRUCTURE'),
  47:dict(upto='pb',title='WAIT FOR THE RETURN',sub='Let price come back into the support zone.',chip='03 / WAIT FOR PRICE'),
  48:dict(upto='ent',title='ENTRY CONFIRMATION',sub='A green candle in the zone.',chip='04 / ENTRY'),
  49:dict(upto='ent',title='PLAN THE TRADE',sub='Stop below the zone. Target near the previous high.',chip='05 / STOP + TARGET'),
  50:dict(upto='t3',title='TARGET 4,500',sub='Price rises, pulls back and taps the same area again.',chip='05 / STOP + TARGET'),
  51:dict(upto='big',title='STRENGTH + STRUCTURE FILTER ZONES',sub='A much bigger move follows.',chip='RESULT')},
 [dict(type='zone',p1=4290,p2=4310,label='SUPPORT ZONE',color=T,idx=0),
  dict(type='tag',idx='t1',price=4292,text='1',dy=36,color=T),dict(type='tag',idx='t2',price=4291,text='2',dy=36,color=T),
  dict(type='arrow',idx='imp',price=4400,dir='up',color=T,text='STRONG MOVE',scene=42,until=44),
  dict(type='hline',price=4380,label='PREVIOUS HIGH',color=G,idx='u1',scene=44),
  dict(type='circle',idx='imp',price=4472,color=G,scene=44,until=47),dict(type='tag',idx='imp',price=4472,text='HIGHER HIGH',dy=-46,color=G,scene=44,until=47),
  dict(type='tag',idx='d1',price=4390,text='BOS',dy=-30,color=T,scene=45,until=47),
  dict(type='tag',idx='u2s',price=4340,text='WEAK BOUNCE: FALLS BACK',dy=70,color=Rd,scene=46,until=47),
  dict(type='tag',idx='pb',price=4310,text='RETURN TO THE ZONE',dy=-44,color=G,scene=47,until=49),
  dict(type='circle',idx='ent',price=4322,color=G,scene=48,until=50),dict(type='tag',idx='ent',price=4322,text='GREEN CANDLE: ENTRY',dy=-54,color=T,scene=48,until=50),
  dict(type='box',id='trade',side='long',entry=4320,stop=4285,target=4470,idx='ent',scene=49,until=50),
  dict(type='box',id='trade',side='long',entry=4320,stop=4285,target=4500,idx='ent',scene=50),
  dict(type='tag',idx='t3',price=4294,text='TAPS THE ZONE AGAIN',dy=48,color=G,scene=50,until=51),
  dict(type='tag',idx='big',price=4562,text='TARGET HIT',dy=-46,color=T,scene=51)])
# ---- I: resistance example (scenes 54,57,59,60,63,64,65,67,68,70-74)
scen('I',SYM,4100,[('a',4128,8,5),('pl',4070,3,3),('b',4132,8,5),('r1',4148,6,4,{'tap_hi':4150}),('d1',4122,5,4),('r2',4147,5,4,{'tap_hi':4150}),('d2',4120,4,4),('r3',4146,4,4,{'tap_hi':4150}),
  ('drop',4022,7,4),('bn',4094,6,3,{'tap_hi':4097}),('react',4058,5,3),('rec',4094,6,3),('brk2',4118,4,3),('tap',4146,4,3,{'tap_hi':4150}),('ent',4120,1,2),
  ('dn1',4078,8,4),('pbk',4090,3,3),('dn2',3998,12,4)],91,
 {54:dict(upto='bn',title='WHICH LEVEL DO YOU MARK?',sub='Several possible levels. It looks confusing.',chip='ZONE CHECK / RESISTANCE'),
  57:dict(upto='bn',title='WHERE DID THE BIG MOVE START?',sub='Find the origin of the strongest downward momentum.',chip='01 / FIND THE ORIGIN'),
  59:dict(upto='bn',title='THE MAIN RESISTANCE',sub='The strongest bearish move began here.',chip='01 / FIND THE ORIGIN'),
  60:dict(upto='bn',title='THE COMBINATION WE WANT',sub='Reactions, a strong move down and a break of structure.',chip='02 / THREE REASONS'),
  63:dict(upto='rec',title='WHAT ABOUT THE LOWER LEVEL?',sub='Price reacted, failed to continue and came back up.',chip='03 / WEIGH THE LEVELS'),
  64:dict(upto='rec',title='GIVE MORE WEIGHT TO THE BIG MOVE',sub='The zone that produced the major move matters most.',chip='03 / WEIGH THE LEVELS'),
  65:dict(upto='brk2',title='PRICE BREAKS THE LOWER LEVEL',sub='The main zone is the next important level.',chip='03 / WEIGH THE LEVELS'),
  67:dict(upto='ent',title='REACHING THE MARKED ZONE',sub='A bearish candle: a possible short.',chip='04 / THE TRADE'),
  68:dict(upto='ent',title='STOP ABOVE. TARGET 1:2.',sub='Stop above the candle or the zone, depending on the plan.',chip='04 / THE TRADE'),
  70:dict(upto='ent',title='FOLLOWING THE EXAMPLE',sub='Price tapped our resistance. A red candle appears.',chip='04 / THE TRADE'),
  71:dict(upto='ent',title='TARGET: THE ROUND NUMBER 4,000',sub='Short entry, stop above the area.',chip='04 / THE TRADE'),
  72:dict(upto='ent',title='RISK-TO-REWARD: ROUGHLY 1 : 3.9',sub='In this illustration.',chip='04 / THE TRADE'),
  73:dict(upto='dn1',title='LET\'S SEE WHAT HAPPENS',sub='Price moves down, pulls up briefly, then falls again.',chip='05 / THE OUTCOME'),
  74:dict(upto='dn2',title='TARGET HIT',sub='Zone, strength, structure, return, then evaluate the trade.',chip='05 / THE OUTCOME')},
 [dict(type='hline',price=4148,label='',color='#55657f',dash=1,idx=0,scene=54,until=57),dict(type='hline',price=4095,label='',color='#55657f',dash=1,idx=0,scene=54,until=57),dict(type='hline',price=4070,label='',color='#55657f',dash=1,idx=0,scene=54,until=57),
  dict(type='arrow',idx='r3',price=4150,dir='down',color=Rd,text='STRONGEST SELL-OFF STARTS HERE',scene=57,until=59),
  dict(type='zone',p1=4140,p2=4152,label='MAIN RESISTANCE',color=G,idx=0,scene=59),
  dict(type='tag',idx='r1',price=4150,text='1',dy=-30,color=G,scene=60,until=63),dict(type='tag',idx='r2',price=4150,text='2',dy=-30,color=G,scene=60,until=63),dict(type='tag',idx='r3',price=4150,text='3',dy=-30,color=G,scene=60,until=63),
  dict(type='hline',price=4070,label='PREVIOUS LOW',color=Rd,idx='pl',scene=60),dict(type='tag',idx='drop',price=4040,text='BOS: TAKES OUT THE LOW',dy=60,color=Rd,scene=60,until=63),
  dict(type='hline',price=4095,label='LOWER LEVEL',color='#8aa0c4',idx='bn',scene=63),dict(type='tag',idx='react',price=4058,text='FAILED TO CONTINUE',dy=50,color='#8aa0c4',scene=63,until=65),
  dict(type='tag',idx='bn',price=4152,text='MORE WEIGHT',dy=-48,color=G,scene=64,until=65),
  dict(type='tag',idx='brk2',price=4118,text='BREAKS THE LOWER LEVEL',dy=70,color=T,scene=65,until=67),
  dict(type='circle',idx='ent',price=4120,color=Rd,scene=67,until=71),dict(type='tag',idx='ent',price=4152,text='BEARISH CANDLE',dy=-48,color=Rd,scene=67,until=71),
  dict(type='box',id='trade',side='short',entry=4120,stop=4151,target=4058,idx='ent',scene=68,until=71),
  dict(type='box',id='trade',side='short',entry=4120,stop=4151,target=4000,idx='ent',scene=71,rr='RR 1 : 3.9',rrscene=72),
  dict(type='tag',idx='dn2',price=3998,text='TARGET HIT',dy=48,color=T,scene=74)],pad=40)
# ---- M: swing trading alerts (scene 78)
scen('M',SYM,4200,[('a',4300,10,6),('b',4255,6,6),('c',4262,5,5),('d',4350,10,6),('e',4310,6,6)],101,
 {78:dict(upto='e',title='SWING TRADING: MARK ZONES, SET ALERTS',sub='A one-hour chart can be planned in advance.',chip='SWING PLAN / ONE-HOUR CHART')},
 [dict(type='zone',p1=4250,p2=4264,label='ALERT ZONE (SUPPORT)',color=T,idx=0),dict(type='zone',p1=4346,p2=4360,label='ALERT ZONE (RESISTANCE)',color=Rd,idx=0),
  dict(type='box',id='sw',side='long',entry=4268,stop=4244,target=4340,idx='c',scene=78)])
# ---- N: support -> resistance, retest short (scenes 81,82,85,87-94)
scen('N',SYM,4380,[('a1',4322,6,5),('s1',4304,5,4,{'tap_lo':4300}),('imp1',4400,8,5),('d1',4342,6,5),('s2',4306,6,4,{'tap_lo':4300}),('imp2',4440,8,5),('d2',4352,8,5),('s3',4312,5,4,{'tap_lo':4301}),
  ('brk',4200,9,6),('rt',4296,10,5,{'tap_hi':4308}),('ent1',4290,1,2),('dn',4235,8,5),('up2',4294,9,5,{'tap_hi':4309}),('ent2',4283,1,2),('spk',4324,3,6),('fall',4170,14,6)],111,
 {81:dict(upto='imp2',title='A STRONG SUPPORT',sub='A major bullish move started here and made a higher high.',chip='ROLE REVERSAL / SUPPORT TO RESISTANCE'),
  82:dict(upto='brk',title='THEN THE SUPPORT BREAKS',sub='What should we look for now?',chip='ROLE REVERSAL / SUPPORT TO RESISTANCE'),
  85:dict(upto='brk',title='HOW STRONG WAS THE BREAKDOWN?',sub='Did sellers take control? Did price break an important low?',chip='CHECK / BREAKDOWN STRENGTH'),
  87:dict(upto='rt',title='RETEST OF THE OLD SUPPORT',sub='It may now act as resistance.',chip='RETEST / THE PLAN'),
  88:dict(upto='ent1',title='A POSSIBLE SHORT',sub='Stop above the resistance zone. Target near 4,200.',chip='RETEST / THE PLAN'),
  89:dict(upto='up2',title='PRICE MOVES DOWN, THEN RETESTS AGAIN',sub='We keep watching the same zone.',chip='RETEST / SECOND TEST'),
  90:dict(upto='up2',title='WHY THIS LEVEL?',sub='Strong selling and a break of structure to the downside.',chip='RETEST / SECOND TEST'),
  91:dict(upto='ent2',title='WAIT FOR A BEARISH CANDLE',sub='There it is.',chip='RETEST / ENTRY'),
  92:dict(upto='ent2',title='THE SHORT TRADE',sub='Stop above that candle. Target around 4,200.',chip='RETEST / ENTRY'),
  93:dict(upto='spk',title='THE STOP LOSS IS HIT',sub='We lose this trade.',chip='RETEST / RESULT'),
  94:dict(upto='fall',title='STOP PLACEMENT MATTERS',sub='A wider stop above the full zone would have changed the result.',chip='RETEST / LESSON')},
 [dict(type='zone',p1=4300,p2=4312,label='SUPPORT',color=T,idx=0,to='s3'),dict(type='zone',p1=4300,p2=4312,label='NOW RESISTANCE',color=Rd,idx='brk'),
  dict(type='arrow',idx='imp1',price=4400,dir='up',color=T,text='MAJOR BULLISH MOVE',scene=81,until=82),dict(type='tag',idx='imp2',price=4442,text='BULLISH BOS',dy=-44,color=G,scene=81,until=82),
  dict(type='tag',idx='brk',price=4210,text='SUPPORT BREAKS',dy=60,color=Rd,scene=82,until=87),
  dict(type='hline',price=4304,label='IMPORTANT LOW',color=Rd,idx='s1',scene=85,until=89),dict(type='tag',idx='brk',price=4250,text='STRONG SELLING + BOS DOWN',dy=68,color=Rd,scene=85,until=87),
  dict(type='tag',idx='rt',price=4308,text='RETEST',dy=-44,color=G,scene=87,until=89),
  dict(type='circle',idx='ent1',price=4290,color=Rd,scene=88,until=89),dict(type='box',id='h1',side='short',entry=4290,stop=4318,target=4200,idx='ent1',scene=88,until=89,dashed=1),
  dict(type='tag',idx='up2',price=4309,text='TESTS THE ZONE AGAIN',dy=-44,color=G,scene=89,until=91),
  dict(type='circle',idx='ent2',price=4283,color=Rd,scene=91,until=93),
  dict(type='box',id='trade',side='short',entry=4283,stop=4301,target=4200,idx='ent2',scene=92),
  dict(type='tag',idx='spk',price=4324,text='STOP HIT',dy=-44,color=Rd,scene=93,until=94),
  dict(type='hline',price=4330,label='WIDER STOP',color=G,idx='ent2',scene=94,dash=1),dict(type='tag',idx='fall',price=4170,text='PRICE FALLS ANYWAY',dy=52,color=T,scene=94)],pad=40)
# ---- P: resistance -> support, retest long (scenes 99,100,108-111)
scen('P',SYM,4100,[('a',4040,6,5),('s1',4006,5,4,{'tap_lo':4000}),('u1',4110,7,5),('r1',4146,5,4,{'tap_hi':4150}),('d1',4090,6,5),('s2',4008,6,4,{'tap_lo':4000}),('u2',4140,8,5),('r2',4148,4,4,{'tap_hi':4150}),('d2',4100,4,4),
  ('brk',4240,6,4),('pb',4156,10,5,{'tap_lo':4150}),('ent',4172,1,2),('big',4310,12,4)],121,
 {99:dict(upto='d2',title='A STRONG SUPPORT',sub='Price found support here several times.',chip='ROLE REVERSAL / RESISTANCE TO SUPPORT'),
  100:dict(upto='brk',title='RESISTANCE BREAKS',sub='Price tested it before. Now it breaks through.',chip='ROLE REVERSAL / RESISTANCE TO SUPPORT'),
  108:dict(upto='brk',title='THE OLD RESISTANCE MAY BE SUPPORT',sub='A bullish candle on the retest may be a buy.',chip='RETEST / THE PLAN'),
  109:dict(upto='pb',title='PRICE COMES BACK AND TOUCHES THE AREA',sub='We wait for confirmation.',chip='RETEST / THE TOUCH'),
  110:dict(upto='ent',title='THE LONG TRADE',sub='Buy on the bullish candle. Stop below the zone. Target above.',chip='RETEST / ENTRY'),
  111:dict(upto='big',title='A VERY STRONG MOVE',sub='Strength and structure paid off here.',chip='RETEST / RESULT')},
 [dict(type='zone',p1=4000,p2=4012,label='STRONG SUPPORT',color=T,idx=0),dict(type='arrow',idx='s1',price=4000,dir='up',color=T,text='STRONG MOVE',scene=99,until=100),
  dict(type='hline',price=4150,label='RESISTANCE',color=Rd,idx='r1',to='d2',scene=99),
  dict(type='tag',idx='brk',price=4240,text='BREAKS RESISTANCE',dy=-46,color=T,scene=100,until=109),
  dict(type='hline',price=4150,label='NOW SUPPORT',color=T,idx='brk',scene=108),
  dict(type='tag',idx='pb',price=4150,text='RETEST',dy=44,color=T,scene=109,until=111),
  dict(type='circle',idx='ent',price=4172,color=T,scene=110,until=111),
  dict(type='box',id='trade',side='long',entry=4172,stop=4140,target=4270,idx='ent',scene=110),
  dict(type='tag',idx='big',price=4312,text='TARGET HIT',dy=-46,color=T,scene=111)],pad=40)
# chart scene -> scenario id
SCENE2CH={}
for cid,sc in S.items():
    for k in sc['beats']:SCENE2CH[k]=cid
if __name__=='__main__':
    import json
    exp={'7','8','9','12','14','16','17','18','37','42','44','45','46','47','48','49','50','51','54','57','59','60','63','64','65','67','68','70','71','72','73','74','78','81','82','85','87','88','89','90','91','92','93','94','99','100','108','109','110','111'}
    # scenes with no explicit beat inherit the previous beat of the same chart (70,71.. defined; check)
    miss=sorted(int(x) for x in exp if int(x) not in SCENE2CH)
    print({k:len(v['candles']) for k,v in S.items()},'missing',miss)
