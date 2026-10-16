"""Live regression checks for numeric grounding and the existing tool pipelines."""
# Learning guide:
# Combine three live extraction/tool regressions with nine saved audit checks.
# Requires existing input-audit-before.json and input-audit-after.json.
# Running the script replaces input-fix-verification.json; development evidence only.
import json
from datetime import date
from pathlib import Path
from time import perf_counter
from main import extract_profile
from seller_profile import extract_seller_profile
from vehicle_frame import load_vehicles
from valuation import estimate_vehicle_value
from matching import filter_vehicles
from scoring import rank_vehicles

ROOT=Path(__file__).resolve().parent
CASES=[
    ('buyer_normal','buyer','Budget RM50000, at least five seats, mainly city commuting. Fuel economy and a spacious boot are high priorities.',{'budget_myr':50000,'required_seats':5,'usage':['city_commute'],'fuel_priority':'high','space_priority':'high'}),
    ('seller_normal','seller','I want to sell my Perodua Alza 1.5 SE, manufactured in 2020, automatic, 90000 km, fair condition. No major accident and no flood damage.',{'mileage_km':90000,'year':2020,'major_accident_reported':False,'flood_damage_reported':False}),
    ('buyer_foreign_keep_other_facts','buyer','Budget USD50000, five seats, city commuting.',{'budget_myr':None,'required_seats':5,'usage':['city_commute']}),
]

if __name__=='__main__':
    cars=load_vehicles(ROOT/'data'/'vehicles_real.json')
    records=[]
    for name,kind,text,expected in CASES:
        start=perf_counter()
        try:
            p=extract_profile(text,'qwen3:4b') if kind=='buyer' else extract_seller_profile(text)
            actual=p.model_dump()
            errors={k:{'expected':v,'actual':actual[k]} for k,v in expected.items() if actual[k]!=v}
            result=rank_vehicles(p,filter_vehicles(p,cars)) if kind=='buyer' else estimate_vehicle_value(p,cars,as_of=date(2026,10,15))
            wanted_status={'buyer_normal':'matches_found','seller_normal':'reference_only','buyer_foreign_keep_other_facts':'needs_clarification'}[name]
            if result['status']!=wanted_status:
                errors['status']={'expected':wanted_status,'actual':result['status']}
            record={'case':name,'input':text,'expected':expected,'actual':actual,'errors':errors,'passed':not errors,'tool_status':result['status']}
        except Exception as error:
            record={'case':name,'passed':False,'error':str(error)}
        record['seconds']=round(perf_counter()-start,2)
        records.append(record)
        print(name,'PASS' if record['passed'] else 'FAIL',record.get('errors',{}),flush=True)
    before=json.loads((ROOT/'input-audit-before.json').read_text(encoding='utf-8'))
    after=json.loads((ROOT/'input-audit-after.json').read_text(encoding='utf-8'))
    expectations={'seller_900m':{'mileage_km':0.9},'seller_50000m':{'mileage_km':50},'seller_miles':{'mileage_km':1448.4096},
                  'seller_no_unit':{'mileage_km':None},'seller_registration':{'year':None},
                  'seller_ambiguous_damage':{'major_accident_reported':None,'flood_damage_reported':None},
                  'buyer_usd':{'budget_myr':None},'buyer_monthly_total':{'budget_myr':50000},'buyer_no_currency':{'budget_myr':None}}
    audit=[]
    for item in after:
        expected=expectations[item['case']]
        actual=item.get('actual',{})
        audit.append({'case':item['case'],'expected':expected,'actual':{k:actual.get(k) for k in expected},
                      'passed':not item.get('error') and all(actual.get(k)==v for k,v in expected.items())})
    output={'model':'qwen3:4b','post_fix_audit_checks':audit,'pipeline_regressions':records,
            'passed':all(r['passed'] for r in records+audit)}
    (ROOT/'input-fix-verification.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8')
    print('Audit checks:',sum(r['passed'] for r in audit),'/',len(audit))
    raise SystemExit(0 if output['passed'] else 1)
