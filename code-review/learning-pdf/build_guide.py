from pathlib import Path
import html, textwrap, hashlib, json
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle

ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'deliver/ME_v7_src'
OUT=Path.home()/'Downloads/PLC_Energy_Manager_v7_Explained.pdf'
ASSETS=Path(__file__).parent
OUT.parent.mkdir(exist_ok=True)
for name,file in [('Body','segoeui.ttf'),('Bold','segoeuib.ttf'),('Mono','consola.ttf')]:
    pdfmetrics.registerFont(TTFont(name,str(Path('C:/Windows/Fonts')/file)))
W,H=A4; LEFT=45; RIGHT=W-45; WIDTH=RIGHT-LEFT
NAVY=colors.HexColor('#17324d'); TEAL=colors.HexColor('#087e8b'); PALE=colors.HexColor('#edf5f8'); INK=colors.HexColor('#25394a')
c=canvas.Canvas(str(OUT),pagesize=A4)
c.setTitle('PLC Energy Manager v7 Explained')
c.setAuthor('PLC Hackathon team • code learning guide')
page=0; y=0; headings=[]
sty=ParagraphStyle('body',fontName='Body',fontSize=10.2,leading=15,textColor=INK,spaceAfter=8)
small=ParagraphStyle('small',parent=sty,fontSize=8.4,leading=12)

def para(s,style=sty):
    global y
    p=Paragraph(s,style); _,h=p.wrap(WIDTH,1000)
    if y-h<52: raise RuntimeError(f'Page {page} overflow before {s[:70]}')
    p.drawOn(c,LEFT,y-h); y-=h+9
def sub(s):
    global y
    y-=5; c.setFillColor(TEAL); c.setFont('Bold',12); c.drawString(LEFT,y,s); y-=22
def code(s,label='Pseudocode',size=8.0):
    global y
    raw=s.expandtabs(2).strip('\n').splitlines(); lines=[]
    for line in raw:
        if len(line)>96:
            indent=' '*min(len(line)-len(line.lstrip())+3,18)
            lines.extend(textwrap.wrap(line,width=96,subsequent_indent=indent,replace_whitespace=False,drop_whitespace=False) or [''])
        else: lines.append(line)
    lh=size*1.42; h=len(lines)*lh+30
    if y-h<52: raise RuntimeError(f'Page {page} code overflow ({len(lines)} lines)')
    c.setFillColor(PALE); c.roundRect(LEFT,y-h,WIDTH,h,5,fill=1,stroke=0)
    c.setFillColor(TEAL); c.setFont('Bold',8); c.drawString(LEFT+10,y-13,label)
    c.setFillColor(INK); c.setFont('Mono',size)
    yy=y-28
    for line in lines: c.drawString(LEFT+10,yy,line); yy-=lh
    y-=h+13
def excerpt(file,start,end):
    lines=(SRC/file).read_text(encoding='utf-8-sig').splitlines()
    code('\n'.join(f'{n:03}  {lines[n-1]}' for n in range(start,min(end,len(lines))+1)),f'Actual ST • {file} • lines {start}–{min(end,len(lines))}',7.4)
def findexcerpt(file,needle,count=10):
    lines=(SRC/file).read_text(encoding='utf-8-sig').splitlines()
    start=next(i+1 for i,v in enumerate(lines) if needle in v)
    excerpt(file,start,start+count-1)
def table(rows,widths=None):
    global y
    data=[[Paragraph(html.escape(str(cell)),small) for cell in row] for row in rows]
    t=Table(data,colWidths=widths or [WIDTH/len(rows[0])]*len(rows[0]),hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),NAVY),('TEXTCOLOR',(0,0),(-1,0),colors.white),('VALIGN',(0,0),(-1,-1),'TOP'),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,PALE]),('BOTTOMPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,0),1,TEAL)]))
    # Paragraph text colours must be explicit in the header.
    for cell in data[0]: cell.style=ParagraphStyle('head',parent=small,textColor=colors.white,fontName='Bold')
    _,h=t.wrap(WIDTH,1000)
    if y-h<52: raise RuntimeError(f'Page {page} table overflow')
    t.drawOn(c,LEFT,y-h); y-=h+13
def new(title,kicker='LEARNING GUIDE'):
    global page,y
    if page: footer(); c.showPage()
    page+=1; headings.append((page,title)); y=H-49
    c.bookmarkPage(f'page{page}')
    c.addOutlineEntry(title,f'page{page}',level=0)
    c.setFillColor(TEAL); c.setFont('Bold',8.5); c.drawString(LEFT,y,kicker); y-=29
    c.setFillColor(NAVY); c.setFont('Bold',20); c.drawString(LEFT,y,title); y-=22
    c.setStrokeColor(TEAL); c.setLineWidth(2); c.line(LEFT,y,RIGHT,y); y-=22
def footer():
    c.setStrokeColor(colors.HexColor('#dce5eb')); c.setLineWidth(.5); c.line(LEFT,38,RIGHT,38)
    c.setFillColor(INK); c.setFont('Body',8); c.drawString(LEFT,25,'Frozen ME v7 source • 7 November 2026')
    c.drawRightString(RIGHT,25,str(page))
def flow(nodes,filename):
    global y
    # Vector flowchart plus editable Mermaid source, using identical node sequence.
    m='flowchart TD\n'+'\n'.join(f'  N{i}["{v}"]' for i,v in enumerate(nodes))+'\n'+'\n'.join(f'  N{i} --> N{i+1}' for i in range(len(nodes)-1))+'\n'
    (ASSETS/filename).write_text(m,encoding='utf-8')
    boxh=42; gap=20; height=len(nodes)*(boxh+gap)-gap
    if y-height<52: raise RuntimeError('diagram overflow')
    x=LEFT+35; bw=WIDTH-70
    for i,v in enumerate(nodes):
        top=y-i*(boxh+gap)
        c.setFillColor(PALE if i%2==0 else colors.HexColor('#dceef0')); c.setStrokeColor(TEAL)
        c.roundRect(x,top-boxh,bw,boxh,7,fill=1,stroke=1)
        c.setFont('Bold',9.5); c.setFillColor(NAVY); c.drawCentredString(x+bw/2,top-25,v)
        if i<len(nodes)-1:
            mid=x+bw/2; c.setStrokeColor(TEAL); c.line(mid,top-boxh,mid,top-boxh-gap+4)
            p=c.beginPath(); p.moveTo(mid-4,top-boxh-gap+8);p.lineTo(mid,top-boxh-gap+3);p.lineTo(mid+4,top-boxh-gap+8);c.drawPath(p)
    y-=height+18

new('Understand your energy manager','PLC HACKATHON • VERIFIED V7')
para('A practical guide to the code you wrote: what it observes, how it chooses battery power, how it protects the grid, and how it proves the result.')
flow(['Simulator supplies current conditions + previous actual flows','Team_Main logs the previous interval and prepares limits','Forecast + planner request a battery action','GridGuard checks the current physical balance','Commands return to simulator; HMI exposes the story'],'architecture.mmd')
sub('The version this guide explains')
para('<b>Frozen source:</b> deliver/ME_v7_src/ — the verified v7 cap-floor version. It does not describe later code optimisations or the evolving WebVisu screen project.')
table([['Scenario','Verified annual cost','Safety / EV'],['S1 — two tariff','€204,598.62','No trip / 100% EV'],['S2 — day ahead','€169,833.86','No trip / 100% EV']],[150,170,WIDTH-320])
para('Read pages 3–7 first for the essentials. Pages 8–22 explain the controller. The final reference pages connect every source file to its role.',small)

new('A route through the guide')
table([['Pages','What you learn'],['3–5','Power, energy, sign conventions, simulated time, and how to read ST'],['6–8','Team_Main, feasible physical limits, EV policy and strategy setup'],['9–10','How the code learns a forecast without embedded load/PV profiles'],['11–15','Peak cap, dynamic programming, first action, and v7 cap floor'],['16–17','Grid protection and a numerical worked example'],['18–20','Energy/cost accounting and the EV-departure workaround'],['21–23','HMI data, trends/alarms, tests, results and practical limitations'],['24–25','Every source file, grouped by responsibility'],['26 onward','Actual source excerpts for supporting files and tuning constants']],[65,WIDTH-65])
sub('Three things to keep separate')
para('<b>Simulator:</b> the organiser’s model of the plant and its measurements. <b>Controller:</b> our code that chooses setpoints. <b>HMI:</b> the screen that displays values and sends permitted control actions. A browser does not run the optimisation.')
para('<b>Pseudocode</b> in this guide is simplified English-like logic. Boxes labelled <b>Actual ST</b> are copied from the frozen source with original line numbers. Diagrams are vector flowcharts; editable Mermaid versions are saved beside the generator.')

new('1 · The plant and the power balance')
para('A site consumes electricity, generates solar power, charges vehicles, and has a battery. The controller chooses battery charging/discharging and sometimes reduces solar output. It tries to reduce the annual bill while delivering EV energy and avoiding a grid trip.')
table([['Symbol / acronym','Meaning and units'],['FNE / PV','Fotonaponska elektrana: solar generation, kW'],['FEC','The site’s fixed consumption/load, kW'],['BESS','Battery energy storage system: 1500 kWh nominal, ±750 kW'],['SoC','State of charge, %. Allowed range 10–90%'],['EV','Electric vehicle; four chargers, up to 22 kW each'],['EGC / grid','Grid connection: import up to 1000 kW, export up to 499 kW'],['kW versus kWh','kW is power now; kWh is energy accumulated over time']],[150,WIDTH-150])
code('grid = fixed_load - solar + sum(EV_power) - battery_power\n\nbattery_power > 0  means DISCHARGE into the site\nbattery_power < 0  means CHARGE from the site\ngrid > 0           means IMPORT\ngrid < 0           means EXPORT','The key sign convention',9)
para('At 400 kW for one 15-minute interval, energy = 400 × 0.25 = <b>100 kWh</b>. Battery losses mean that bus energy and stored battery energy are different.')

new('2 · Two clocks, one correct sequence')
para('One simulated interval represents <b>15 minutes</b>, but the computer may calculate it in milliseconds. The control result must depend on the simulated step <b>k</b>, not the laptop clock or how quickly the PLC task repeats.')
flow(['At step k: current load, available solar and starting SoC are known','Actual energy-flow readings describe interval k−1','Log k−1 using the remembered date, tariff and fixed load','Choose commands for interval k','At k+1: interval k becomes the previous interval'],'timing.mmd')
para('There are 96 intervals per day and 35,040 per year. At <b>k = 0</b>, reset the controller and logs. At <b>k = 35,040</b>, log the last interval and issue zero commands. Do not accidentally skip that final bookkeeping call.')
para('A normal simulation period is at least 10 ms. Earlier validation also used a 5 ms stress setting; that is a performance check, not the permitted normal setting.',small)

new('3 · Read Structured Text without fear')
table([['ST notation','Plain meaning'],['FUNCTION_BLOCK','A reusable object with memory between calls: forecasts and logs retain state'],['FUNCTION','A helper that calculates a return value; see F_PeakCap and F_StageCost'],['VAR_INPUT / VAR_OUTPUT','Values passed in / values produced by the block'],['VAR_IN_OUT','An argument passed by reference, used here for large arrays'],[':= / = / <>','Assign a value / compare equality / compare inequality'],['IF … THEN … END_IF','Do a block only when a condition is true'],['FOR / WHILE','Repeat instructions; each repetition costs execution time'],['REAL / LREAL','Floating-point number / higher precision floating-point number'],['LIMIT(lo, x, hi)','Clamp x so it stays between lo and hi'],['SEL(flag, a, b)','Returns b when flag is TRUE, otherwise a']],[155,WIDTH-155])
para('A name is a clue: <b>r</b> often marks a REAL, <b>x</b> a BOOL, <b>a</b> an array, <b>i</b> an integer and <b>fb</b> a function-block instance. <b>Req</b> means requested, <b>Act</b> actual, and <b>Prev</b> previous.')
findexcerpt('F_DayType.st','IF ',7)
para('This helper groups Monday–Friday together, Saturday separately, and Sunday separately. The forecast keeps different load profiles for those three day types.')

new('4 · Team_Main is the conductor')
code('if this is a new simulated step:\n  if k == 0: reset state and logs\n  if previous interval exists and k advanced by exactly one:\n    correct EV departure measurements\n    log previous energy, then previous cost\n  if simulation is finished:\n    set every command to zero\n  else:\n    calculate feasible battery / EV limits\n    ask Strategy for requested setpoints\n    pass those requests through GridGuard\n    write a complete command from the guarded values\n    remember inputs needed at k+1\nupdate HMI support data\nreturn the held command','Team_Main in pseudocode',8.4)
findexcerpt('Team_Main.st','k := simOut.t_sim.k;',8)
para('The <b>new-step gate</b> prevents double-counting and repeatedly learning the same observation when the PLC calls the block again. It notices changes in k or the simulated timestamp. The remembered command is still returned on every call.')
para('Notice the order: the energy logger updates monthly peaks before the cost logger prices them; the strategy proposes an action before the guard corrects it. Changing that order changes behaviour.')

new('5 · Physical limits and the EV promise')
para('Before optimisation, Team_Main calculates what the simulator can actually accept. Near the battery’s upper/lower SoC boundary, its feasible power can be much smaller than 750 kW.')
code('usable battery energy = (SoC − minimum SoC) / 100 × capacity\nmax charge = min(750, remaining room / (0.25 × charge efficiency))\nmax discharge = min(750, usable energy × discharge efficiency / 0.25)\n\nEV feasible power = min(22, remaining energy / (0.25 × 0.9))','Feasible bus-side limits',8.2)
para('With 1500 kWh capacity and a 10–90% SoC window, the usable battery window is <b>1200 kWh</b>. Charge and discharge efficiencies are 0.95 each. EV efficiency is 0.9.')
findexcerpt('FB_Strategy.st','sumEv := 0.0;',7)
para('The selected EV policy is simple: <b>charge as soon as possible at the maximum feasible power</b>. It is not a complex deadline scheduler. Remaining time is still computed to prioritise shedding if the grid guard must reduce EV power.')
para('<b>Slack</b> = steps until departure minus the steps needed at full charging power. Larger slack means a car can better tolerate being slowed down. A guard intervention can reduce EV charging to protect the grid; practice-data runs still delivered 100%.')

new('6 · Strategy builds the planning question')
para('FB_Strategy connects all the pieces. In normal operation, iStrategy = 1 selects forecasting and planning. Mode 0 is the simple baseline: charge the battery on solar surplus and discharge on deficit.')
flow(['Choose horizon: at most 96 intervals','Learn current conditions and forecast future net load','Read published prices and add the correct grid fee','Calculate the day-ahead learned cap floor','Plan battery power; curtail exports at negative prices'],'strategy.mmd')
para('Day-ahead prices for tomorrow become visible after 13:00 (quarter-hour 52). Before that, the horizon ends at midnight; after that it may include tomorrow, but the configured 96-step computing limit still applies. The year-end horizon is shortened too.')
para('<b>aCi</b> = energy price + import grid fee. <b>aCe</b> = max(0, 0.9 × energy price). Treating negative-price exports as having no benefit is paired with actual voluntary solar curtailment when exporting would cost money.')

new('7 · Forecasting: learn a normal day')
para('The code contains no embedded future solar or load profiles. It learns from observations already available at the current step. It knows current load and available solar exactly; future values are estimates.')
table([['Memory','Purpose'],['aFec[day type, quarter-hour]','Expected fixed load for weekday / Saturday / Sunday'],['aSig[day type, quarter-hour]','Smoothed absolute load forecast error; a conservative reserve signal'],['aPv[quarter-hour]','Solar profile shared across day types'],['aVt[quarter-hour]','Most recently observed high/low tariff window'],['Recent actual/profile rings','Last four observations for intraday correction']],[190,WIDTH-190])
code('new profile = old profile + alpha × (observation − old profile)\n\nload alpha = 0.5     solar alpha = 0.3\ndeviation alpha = 0.3','Exponential moving average (EMA)',9)
findexcerpt('FB_Forecast.st','IF aFecOk[dtp, q] THEN',10)
para('The variable called sigma is a smoothed <b>absolute deviation</b>, not a statistically exact standard deviation. Cold start matters: when no matching slot has been learned, the load estimate falls back to a learned weekday slot or the highest load observed so far.')

new('8 · Forecasting: adjust for today')
para('A learned profile alone would react slowly to a cloudy day or unusually busy site. Intraday correction compares recent actual observations to their pre-update profile values and scales the forecast accordingly.')
code('load correction = clamp(0.5, recent actual / recent profile, 1.5)\nsolar correction = clamp(0.2, recent actual / recent profile, 1.5)\nfade = exp(−future_step / 16)\nfuture = profile × (1 + (correction − 1) × fade)\n\nexpected net load = fixed load + predicted EV power − solar\npessimistic net = expected + ksig × deviation + (1 − pvf) × solar','Forecast calculation',8.2)
table([['Setting','S1: two tariff','S2: day ahead'],['ksig (load reserve)','0.75','0'],['pvf (solar share trusted)','0.6','0.2'],['Peak penalty uses','Pessimistic net load','Expected net load']],[185,150,WIDTH-335])
para('At future step zero, the forecast uses current actual load and solar, so expected and pessimistic net load are equal. Connected EVs are forecast as charging immediately; future arrivals are not magically known.')
para('A forecast error is expected. That is why the controller replans every interval and why a separate grid guard checks the actual current interval.')

new('9 · Find a plausible monthly peak cap')
para('A large monthly import spike creates a peak charge. If the month has already reached 600 kW, lowering today’s import to 500 kW cannot undo that paid peak. The planner therefore starts with the month’s peak so far as its cap floor.')
code('test(cap):\n  energy = current usable battery energy\n  for each predicted interval:\n    if net_load > cap:\n      discharge enough to hold cap\n      fail if power is too high or energy becomes negative\n    else:\n      recharge below cap, respecting power and capacity\n  succeed\n\nif test(already_paid_peak): return already_paid_peak\notherwise bisect between that peak and the import limit\nreturn feasible cap × 1.02, clamped to the import limit','F_PeakCap in pseudocode',8.3)
para('<b>Bisection</b> repeatedly halves a search range. The code tests the paid peak first, then performs up to 12 refinements. This is a short feasibility simulation, not the full dynamic program.')
findexcerpt('F_PeakCap.st','F_PeakCap := rFloor;',8)
para('This cap is a planning target, not the legal grid limit. A soft penalty discourages crossing it. The independent GridGuard enforces the physical grid constraints.')

new('10 · Dynamic programming: the map')
para('The planner compares battery choices across a horizon, rather than choosing only what looks cheapest this minute. Its dynamic program stores the best future cost for each possible battery energy level.')
flow(['State: usable stored energy, 31 levels from 0 to 1200 kWh','Action: change energy by −4 … +4 levels (40 kWh each)','Transition: energy_next = energy_now + action × 40','Cost: grid energy + soft penalty for import above target','Work backwards; then choose only the first real action'],'dp.mmd')
para('A positive DP action increases stored energy and means charging; the final output rPb uses the opposite convention: positive means bus-side discharge. Efficiencies convert between stored-energy changes and bus power.')
para('<b>Model predictive control:</b> calculate a whole future plan, apply just its first action, then recalculate using the next measurements. The future plan is guidance, not a fixed timetable.')

new('11 · Dynamic programming: the arithmetic')
code('V[last horizon, energy] = −energy × terminal energy value\n\nfor time from horizon−1 backwards to 1:\n  for each allowed action:\n    calculate bus power and stage cost\n  for each of 31 energy states:\n    Vnow[state] = minimum over feasible actions of:\n      stage_cost[action] + Vnext[state + action]\n  Vnext = Vnow','Backward recurrence',8.8)
findexcerpt('FB_Planner.st','FOR iE := 0 TO NS DO',17)
para('The terminal value is 0.9 × the average import price over the horizon. Crediting leftover stored energy reduces the temptation to empty the battery just because the calculation stops at midnight.')
para('Stage cost is import energy × import price, or minus export energy × export value, plus a strong penalty when planned import exceeds the chosen target. That penalty is an <b>internal planning heuristic</b>, not the organiser’s actual peak invoice formula.')
para('The S1 late-discharge tie-breaker increases future import prices by a small factor, 1 + 0.05 × i/96. Within otherwise similar tariff periods, this favours saving battery discharge for later. It is off in S2.')

new('12 · The first action is more precise')
para('The future DP uses a coarse 40 kWh energy grid for speed. The action taken now is evaluated more precisely against current SoC and exact current load/solar.')
code('candidates = 41 powers from max_charge to max_discharge\nalso try:\n  battery power that makes grid power exactly zero\n  battery power that makes import exactly equal to cap\n\nfor each feasible candidate:\n  calculate resulting stored energy\n  interpolate the future DP cost between neighbouring levels\n  add exact first-interval stage cost\nchoose the cheapest candidate\nif import can be kept at cap: enforce that final correction','First action in pseudocode',8.3)
findexcerpt('FB_Planner.st','FOR m := 0 TO N_FIRST - 1 DO',12)
para('Interpolation avoids rounding today’s energy to a single coarse level. There are 41 evenly spaced candidates and up to two extra exact-balance candidates. This explains why the candidate array has room for 43 entries.')
para('The result is a <b>request</b>, not the final command. GridGuard still clamps it to physical limits and checks current import/export.')

new('13 · What v7 adds: a learned cap floor')
para('V7 avoids repeatedly choosing an unrealistically low S2 import target early in a month. A slightly higher target can make cheap charging possible and reduce costly later peaks. This is deliberate trade-off, not a relaxation of the 1000 kW grid limit.')
code('R_day = lowest cap that could have served a measured day\n        starting with a full battery\n\nfloor = min(import_limit,\n            0.95 × mean(last up to 3 completed monthly peaks),\n            1.20 × max(last up to 14 daily R_day values))\n\nactivate only in S2, with at least one completed month\nand at least five daily R_day samples\nplanner target = max(original target, floor)','FB_CapFloor in pseudocode',8.4)
para('The code records current fixed load minus available solar, then adds the previous interval’s actual EV draw when that measurement becomes available. It closes the day before starting the new day’s record.')
para('F_DayReq runs its 14-step bisection when quarter-hour ≥ 14 on the next day (03:30). <b>The verified ST runs that calculation in one call;</b> the delay does not mean one bisection iteration is spread across each of 14 PLC calls.')
findexcerpt('FB_CapFloor.st','rFloor := 0.0;',13)
para('In S1 the output floor is zero. History collection still occurs. The floor is based only on past realised measurements and completed monthly peaks.')

new('14 · GridGuard is the last safety net')
para('Optimisation is allowed to be approximate. Current-interval grid protection cannot wait for last interval’s grid meter: it predicts the bus balance from current load, solar, EV requests and feasible battery power.')
code('clamp all requests to physically feasible values\npredicted_grid = fixed_load − solar + EV_sum − battery\n\nif predicted import is too high:\n  restore voluntarily curtailed solar\n  increase battery discharge / reduce charging\n  reduce EV power, largest slack first\n  flag failure if still above the margin target\n\nif predicted export is too high:\n  reduce discharge / increase charging\n  curtail solar if needed\nrecalculate predicted grid power from final values','GridGuard in pseudocode',8.3)
para('Configured margins are 1 kW: the target import limit is 999 kW and export target is 498 kW, below the hard 1000/499 kW trip limits. The margin is useful headroom, but the code can report that it cannot hold the margin when the underlying physical situation makes it impossible.')
findexcerpt('Team_Main.st','stCmd.BESS_enable_discharge := TRUE;',8)
para('The command starts from an all-zero structure. The IF / ELSIF means charge and discharge enables cannot both become true. Every command member is assigned each call through the held complete structure.')

new('15 · Walk through one interval')
table([['Known at interval k','Example value'],['Fixed consumption','1100 kW'],['Available solar','100 kW'],['EV requests','Two connected vehicles × 22 = 44 kW'],['Planner battery request','0 kW'],['Battery feasible discharge','At least 45 kW']],[250,WIDTH-250])
para('This is an illustrative arithmetic case, not a recorded dataset interval. First predict grid import: <b>1100 − 100 + 44 − 0 = 1044 kW</b>. That exceeds the guard’s 999 kW target.')
code('required correction = 1044 − 999 = 45 kW\nfinal battery power = +45 kW (discharge)\nfinal predicted import = 1100 − 100 + 44 − 45 = 999 kW\n\nOver the 0.25 h interval:\n  imported energy = 999 × 0.25 = 249.75 kWh\n  battery bus delivery = 45 × 0.25 = 11.25 kWh\n  stored energy reduction = 11.25 / 0.95 = 11.842 kWh\n  EV energy into vehicles = 44 × 0.25 × 0.9 = 9.90 kWh','Worked balance',8.8)
para('At k+1, log the actual flows of this interval. If actual import was 999 kW, the import energy logger adds 249.75 kWh. At an energy price of €0.10/kWh and high grid tariff €0.020811/kWh, this interval adds €24.975 purchase cost and about €5.198 grid cost.')
para('If the month previously peaked at 980 kW, the new 999 kW peak increases the peak bill by (999 − 980) × €3.865 = <b>€73.435</b>. This is why one brief power spike matters.')

new('16 · Energy accounting is not control')
para('FB_EnergyLogger sums what actually happened, not what the optimiser hoped would happen. It keeps a daily array of 365 rows, monthly array of 12 rows and one yearly aggregate.')
code('energy increment [kWh] = actual power [kW] × 0.25 h\n\nfor the correct previous day and month:\n  add PV, fixed load, charge, discharge, import and export\n  add EV energy per charger and total\n  peak = max(previous peak, actual import power)\ncopy yearly values to Team_Results','Energy logging',8.8)
findexcerpt('FB_EnergyLogger.st','// EV per charger and total',10)
para('<b>LREAL accumulators</b> reduce round-off error over 35,040 additions. Calculations used for planning can be REAL for performance, while official totals need higher numerical care.')
para('Team_Log is the detailed history. Team_Results is the official yearly interface with required names such as E_fne and E_import. The HMI can show copies of selected rows; those copies are not the authoritative energy history.')
para('EV energy here is charger bus-side energy. The simulator separately tracks energy delivered into vehicles, including its EV efficiency. Comparing those numbers without understanding that distinction can look like a bug when it is not.')

new('17 · The actual electricity bill')
table([['Component','What the logger calculates'],['Purchase','Import kWh × energy price'],['Export revenue','Export kWh × 0.9 × energy price'],['Grid fee','Import kWh × tariff fee; no fee on export'],['Monthly peak','Maximum monthly import kW × €3.865/kW'],['Daily total','Purchase − revenue + grid fee (no peak allocation)'],['Monthly/yearly total','Purchase − revenue + grid fee + peak']],[155,WIDTH-155])
findexcerpt('FB_CostLogger.st','cBuy :=',3)
para('High-tariff grid fee is €0.020811/kWh; low tariff is €0.010404/kWh. The energy price itself comes from the selected two-tariff or day-ahead table.')
para('The cost logger must run <b>after</b> the energy logger because it reads the updated monthly import peak. Yearly peak cost is the sum of all 12 monthly peak costs, not the single highest annual peak times one price.')
para('A negative price can make import purchase cost negative. Export revenue can also be negative, which adds cost after subtraction. The runtime logger uses the real price formula; the strategy tries to avoid unwanted export at negative prices.')

new('18 · Why remember previous values?')
para('At the start of k, current fixed load belongs to k, but actual PV, battery and grid flows describe k−1. Pairing them directly would create an accounting error, particularly across midnight or month boundaries.')
table([['At k','Correct source when logging k−1'],['Fixed load','Remembered rFecPrev'],['Date / tariff','Remembered iDayPrev, iMonthPrev, xHighPrev'],['Actual PV / BESS / grid','Simulator’s previous-step actual values'],['EV departure interval','Actual EV power, with the special correction below']],[190,WIDTH-190])
findexcerpt('Team_Main.st','IF xLogNow AND aEvConnPrev[j]',5)
para('The simulator clears EV actual power when the vehicle departs, even though the just-completed interval still counted charging energy. The controller therefore substitutes its previous feasible, guard-approved EV command for that departure interval.')
para('This is a narrow workaround for a simulator publication quirk. It does not generally replace actual measurements with requested values. The command used was already clamped to the same physical feasibility limits.')
para('The final k=35,040 call is essential: it logs interval 35,039. Reset clears the histories before any old interval can leak into a new year.')

new('19 · HMI support: data before screens')
para('FB_HmiUpdate publishes a convenient view of controller data into Team_HMI. These variables support native visualisation or WebVisu screens, but this frozen source snapshot does not contain a completed browser dashboard.')
table([['View','What it should explain to the operator'],['Header','Simulated date/time, progress, tariff and price mode'],['Power flows','Requests for k versus actual flows for k−1'],['Battery and EVs','SoC, direction, charger state, departure and remaining energy'],['Tables','Selected day/month and all days of selected month'],['Trends','96 samples = 24 simulated hours'],['Alarms','Current flags plus timestamped message history']],[135,WIDTH-135])
findexcerpt('FB_HmiUpdate.st','Team_HMI.aTrFne[95]',7)
para('Trend arrays shift left once per new simulated step. Index 95 is the newest sample, index 0 the oldest. The SoC trend stores the current starting SoC, which is the previous interval’s ending state; flow samples are actual interval k−1 values.')
para('A WebVisu browser only displays values and sends allowed button writes. The battery optimiser still runs in the PLC/runtime. HMI writes to simulator controls must go through SimCtrl; selection variables choose which logged rows to display.')

new('20 · Alarms and diagnostic evidence')
para('Alarms are not all failures. Some messages report normal protective actions, such as solar curtailment to avoid export overload. The code detects rising edges so a persistent condition does not fill history every interval.')
table([['Code','Meaning'],['1 / 2','Actual import / export overload'],['3 / 4','Simulation tripped / finished'],['5','EV left with undelivered energy'],['6','Grid protection reduced EV charging'],['7','Grid protection curtailed solar'],['8','Predicted import still exceeds the guard target']],[95,WIDTH-95])
findexcerpt('F_AlarmPush.st','FOR i := 49',10)
para('The history holds 50 messages, newest at index 0. When a new message arrives, older entries shift toward index 49 and the oldest is discarded. nAlarms is a cumulative count, so it may exceed the number of retained entries.')
para('Useful diagnostic counters include guard interventions, both battery enables, prediction error and step counts. Compare a stored prediction for k−1 with actual grid flow for k−1: matching timestamps matters as much as matching units.')

new('21 · What the verified results prove')
table([['Measure','S1 — two tariff','S2 — day ahead'],['Annual cost','€204,598.62','€169,833.86'],['Year completed','Yes','Yes'],['Grid trip','No','No'],['EV delivery','100.000%','100.000%'],['Max logged deviation','0.00001%','0.00000%'],['Change from v6','Unchanged','−€355.50 (0.209%)']],[190,150,WIDTH-340])
para('These are practice-data simulator results, not a guarantee for every unseen dataset or real installation. The v7 candidate came from a robustness evaluation, and this port was then confirmed in Machine Expert.')
para('The LP lower-bound reference uses perfect foresight: about €199,779 for S1 and €162,592 for S2. Our rolling controller does <b>not</b> call that LP or know future load/solar. Its gap is about 2.41% and 4.45%, respectively; part of the gap is the unavoidable value of better future knowledge.')
para('Steady 5 ms stress-run throughput was roughly 5.8–6.0 ms per interval including simulator work. S1 took 216 s/year; S2 263 s/year with a slower start. These are wall-time throughput estimates, not instrumented worst-case PLC execution times.')
para('Open delivery issues: complete/test/package the HMI; verify WebVisu acceptance with organisers; resolve evaluation price-table assumptions. Keep the verified archive intact while trying later optimisations.')

new('22 · Every file has a job (1 of 2)','SOURCE MAP • deliver/ME_v7_src')
table([['File','Responsibility'],['Team_Main.st','Sequences reset, previous-step logging, control, memory and HMI calls'],['FB_Strategy.st','Chooses horizon, EV requests, forecast, prices, cap floor and battery planner'],['FB_Forecast.st','Learns load/solar profiles and generates expected/pessimistic net load'],['FB_Planner.st','Calculates cap and backward DP, then chooses continuous first action'],['FB_CapFloor.st','Learns bounded S2 cap floor from daily requirements and completed peaks'],['FB_GridGuard.st','Clamps requests and corrects current import/export violations'],['FB_EnergyLogger.st','Accumulates actual daily/monthly/yearly energy and import peaks'],['FB_CostLogger.st','Accumulates real purchase, revenue, grid and peak costs'],['FB_HmiUpdate.st','Publishes screen values, selected rows, trends and alarm edges'],['F_PeakCap.st','Searches for lowest forecast-feasible cap from current battery energy'],['F_DayReq.st','Searches realised-day cap assuming initially full battery'],['F_StageCost.st','Planner’s energy cost plus soft cap penalty'],['F_EnergyPrice.st','Selects two-tariff or day-ahead price for a given interval']],[155,WIDTH-155])

new('23 · Every file has a job (2 of 2)','SOURCE MAP • deliver/ME_v7_src')
table([['File','Responsibility'],['F_BessMaxChg.st','Feasible charge limit from SoC, efficiency and remaining room'],['F_BessMaxDch.st','Feasible discharge limit from SoC, efficiency and usable energy'],['F_DayType.st','Maps weekday number to weekday/Saturday/Sunday class'],['F_DtString.st','Formats simulated date/time; does not read system clock'],['F_Pad2.st','Adds a leading zero for date/time components'],['F_AlarmPush.st','Inserts one message into the 50-entry history'],['Team_Cfg.st','Tuning constants and safety margins'],['Team_Prices.st','Two-tariff prices and 35,040 day-ahead prices; no load/PV profile'],['Team_HMI.st','Public display/selection/trend/alarm variables'],['Team_Log.st','Daily/monthly/yearly aggregate storage'],['Team_Results.st','Official yearly result interface plus equivalent cost names'],['typeTeamAgg.st','Data type for one energy/cost/peak aggregate'],['typeTeamAlarm.st','Data type for one timestamped alarm/message']],[155,WIDTH-155])
para('<b>Reading order:</b> Team_Main → FB_Strategy → FB_Forecast → FB_Planner → FB_GridGuard. Then read loggers and HMI support. Use the following reference pages to recognise the smaller helpers and data declarations.')

# Each supporting file is represented by actual code, with oversized price data intentionally omitted.
refs=[
('Battery feasibility helpers',[('F_BessMaxChg.st','F_BessMaxChg :=',4),('F_BessMaxDch.st','F_BessMaxDch :=',4)],'LREAL intermediate arithmetic mirrors simulator clamps. The final function return is REAL, matching the strategy interface.'),
('Prices and tariff selection',[('F_EnergyPrice.st','IF iMode = 1 THEN',12),('Team_Prices.st','VAR_GLOBAL',4)],'The enormous day-ahead initializer is not reproduced here. Team_Prices contains 35,040 REAL prices, not an embedded FEC or PV profile. In IEC initializers, repetition notation can compress repeated price values.'),
('Date and small formatting helpers',[('F_DtString.st','// ---IMPL---',17),('F_Pad2.st','// ---IMPL---',8)],'Dates come from the simulator’s DT value. F_DtString converts that supplied timestamp to a human-readable date; F_Pad2 ensures two-digit fields. No wall clock is consulted.'),
('Aggregate and history data types',[('typeTeamAgg.st','STRUCT',18),('typeTeamAlarm.st','STRUCT',7)],'One aggregate row contains energies, four charger energies, import peak and cost components. One alarm record contains a simulated step, stamp, code and text.'),
('Logs and official totals',[('Team_Log.st','VAR_GLOBAL',7),('Team_Results.st','VAR_GLOBAL',15)],'Team_Log stores detailed history. Team_Results exposes the year totals that are compared to the organiser’s SimScore totals.'),
('HMI variables: display data',[('Team_HMI.st','VAR_GLOBAL',17)],'This is a data interface, not a screen definition. It makes the same underlying values easier to bind to gauges, text fields and trend objects. Read-only values must remain read-only from the HMI.'),
('Tuning: forecast and basic safety',[('Team_Cfg.st','N_STEPS :',18)],'These constants tune expected behaviour. The legal physical plant parameters still come from SimParam. Changing a tuning value requires fresh simulator validation.'),
('Tuning: v7 and planner modes',[('Team_Cfg.st','CAPF_ON_DA',12)],'The learned floor is enabled for day-ahead mode. PLAN_TSPLIT is FALSE in this version; its alternate branch remains in the code but is not the selected algorithm.'),
('Planner stage cost',[('F_StageCost.st','IF rG >= 0.0 THEN',9)],'rG is expected net grid power. rGpen may use a more conservative forecast for penalty evaluation. The soft penalty is an optimisation aid, while the actual bill is calculated independently by FB_CostLogger.'),
('Realised-day cap feasibility',[('F_DayReq.st','FOR n := 1 TO 14 DO',22)],'Every trial starts at full usable energy and walks the recorded day. This is a retrospective feasibility score; it does not claim that the real battery was full at midnight.'),
]
for idx,(title,items,explain) in enumerate(refs,1):
    new(f'Reference {idx} · {title}','ACTUAL CODE EXCERPTS')
    para(explain)
    for file,needle,count in items:
        findexcerpt(file,needle,count)

new('Try explaining it back to yourself')
para('If you can answer these questions, you understand the design rather than just recognising its block names.')
for s in [
 'Why does the code log interval k−1 before choosing the action for k?',
 'Why does a positive battery setpoint reduce grid import?',
 'Why can 11.25 kWh delivered by the battery reduce stored energy by more than 11.25 kWh?',
 'Why does the optimiser remember the monthly peak already reached?',
 'What is the difference between a 999 kW guard target and a 1000 kW legal trip limit?',
 'How can the forecast learn without knowing tomorrow’s solar profile?',
 'Why is the planner’s terminal value useful?',
 'Why does a browser dashboard not replace the PLC program?',
 'What does the special EV-departure correction fix?',
 'Why must an efficiency optimisation be regression-tested even if it looks harmless?']:
    para('• '+s)
sub('A short answer to the whole system')
para('“We learn a forecast from measurements, plan battery use across the available price horizon, protect the current grid balance, and account for actual energy and costs on simulated time. We repeat this every 15-minute interval.”')
para('Generated from the frozen v7 files. Supporting generator, editable Mermaid flowcharts and validation artifacts are in code-review/learning-pdf/. The source archive remains the authoritative executable deliverable.',small)

footer();c.save()
manifest={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(SRC.glob('*.st'))}
(ASSETS/'source_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
(ASSETS/'contents.json').write_text(json.dumps(headings,indent=2),encoding='utf-8')
print(json.dumps({'pdf':str(OUT),'pages':page,'source_files':len(manifest),'sections':headings},indent=2))
