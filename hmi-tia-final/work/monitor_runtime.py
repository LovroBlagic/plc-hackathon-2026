import sys,time,json,csv
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"tools"/"plcsim"))
from crane_sim_test import Sim,read_bays
s=Sim(50124)
root=Path(__file__).parent
expected=json.loads((root/"rand01_expected.json").read_text())
names=["State","Mode","TrDone","TrTotal","MSpec","T","AlarmWord","CraneBusy","Carried","OB30Ticks"]
start=time.time(); rows=[];last_report=-20;seen_run=False
while time.time()-start<1000:
 vals=s.rb(["HMI_IF."+n for n in names]);r=dict(zip(names,vals));r["elapsed"]=round(time.time()-start,2);rows.append(r)
 state=int(r["State"]);seen_run=seen_run or state in (3,7)
 if time.time()-start-last_report>=20:
  print(json.dumps(r),flush=True);last_report=time.time()-start
 if seen_run and state in (5,6):break
 time.sleep(0.5)
b0,b1=read_bays(s)
checks={"done":state==6,"transfer_count":int(r["TrDone"])==expected["transfers"],"MSpec":int(r["MSpec"])==expected["MSpec"],"T":abs(float(r["T"])-expected["T_ds"]/10)<0.1,"bay0":b0==expected["bay0"],"bay1":b1==expected["bay1"]}
result={"dataset":"tools/crane_data/rand_01.json","kind":"synthetic regression dataset, NOT organizer hidden data","trigger":"INIT/AUTO/START clicked in native WinCC HMI","last":r,"checks":checks,"pass":all(checks.values())}
(root/"rand01_runtime_result.json").write_text(json.dumps(result,indent=2))
with (root/"rand01_runtime_trace.csv").open("w",newline="") as f:
 w=csv.DictWriter(f,fieldnames=["elapsed"]+names);w.writeheader();w.writerows(rows)
print("RUNTIME_RESULT "+json.dumps(result),flush=True)
