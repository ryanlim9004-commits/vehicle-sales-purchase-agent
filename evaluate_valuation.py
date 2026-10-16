"""One development smoke case, not a market-accuracy evaluation."""
# Learning guide:
# Run one real-model seller extraction followed by the valuation tool.
# Compare key fields and the saved-snapshot asking median; record latency.
# Running the script replaces stage4-live-result.json; this is not market validation.
import json
from datetime import date
from pathlib import Path
from time import perf_counter
from seller_profile import extract_seller_profile
from vehicle_frame import load_vehicles
from valuation import estimate_vehicle_value

ROOT = Path(__file__).resolve().parent
TEXT = 'I want to sell my Perodua Alza 1.5 SE, manufactured in 2020, automatic, 90000 km, fair condition. No major accident and no flood damage.'

if __name__ == '__main__':
    start = perf_counter()
    try:
        profile = extract_seller_profile(TEXT)
        expected = {'brand':'Perodua','model':'Alza','variant':'1.5 SE','year':2020,'transmission':'Automatic','mileage_km':90000,'condition':'fair','major_accident_reported':False,'flood_damage_reported':False}
        actual = profile.model_dump()
        mismatches = {k:{'expected':v,'actual':actual[k]} for k,v in expected.items() if actual[k] != v}
        result = estimate_vehicle_value(profile,load_vehicles(ROOT/'data'/'vehicles_real.json'),as_of=date(2026,10,15))
        passed = not mismatches and result['status']=='reference_only' and result['reference']['median_asking_price_myr']==44800
        record = dict(model='qwen3:4b', input=TEXT, expected=expected, actual=actual,mismatches=mismatches,passed=passed,result=result)
    except Exception as error:
        record = dict(passed=False,error=str(error))
    record['seconds'] = round(perf_counter()-start,2)
    (ROOT/'stage4-live-result.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print('PASS' if record['passed'] else 'FAIL',record['seconds'],'seconds')
    raise SystemExit(0 if record['passed'] else 1)
