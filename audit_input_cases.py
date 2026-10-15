"""Repeatable development audit; captures pre-fix evidence without valuations."""
import json
from pathlib import Path
from time import perf_counter
from seller_profile import extract_seller_profile
from main import extract_profile

ROOT = Path(__file__).resolve().parent
SELLER = 'I want to sell my Perodua Alza 1.5 SE, manufactured in 2020, automatic, {distance}, fair condition. No major accident and no flood damage.'
CASES = [
    ('seller_900m', 'seller', SELLER.format(distance='900m')),
    ('seller_50000m', 'seller', SELLER.format(distance='50000 m')),
    ('seller_miles', 'seller', SELLER.format(distance='900 miles')),
    ('seller_no_unit', 'seller', SELLER.format(distance='odometer 90000, unit not specified')),
    ('seller_registration', 'seller', 'I want to sell a Perodua Alza 1.5 SE, registered in 2021, automatic, 90000 km, fair condition. Manufacturing year is unknown.'),
    ('seller_ambiguous_damage', 'seller', 'I want to sell my 2020 Perodua Alza 1.5 SE automatic, 90000 km, good condition. I am not sure whether it had a major accident or flood damage.'),
    ('buyer_usd', 'buyer', 'Budget USD50000, five seats, city commuting.'),
    ('buyer_monthly_total', 'buyer', 'My monthly budget is RM800, and my maximum total purchase budget is RM50000. Five seats, city commuting.'),
    ('buyer_no_currency', 'buyer', 'Budget 50000, five seats, city commuting. Currency not specified.'),
]

if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--output', default='input-audit-before.json')
    args=parser.parse_args()
    records=[]
    for name,kind,text in CASES:
        start=perf_counter()
        try:
            result=(extract_seller_profile(text) if kind=='seller' else extract_profile(text,'qwen3:4b')).model_dump()
            record={'case':name,'input':text,'actual':result}
            print(name,json.dumps(result,ensure_ascii=True),flush=True)
        except Exception as error:
            record={'case':name,'input':text,'error':str(error)}
            print(name,'ERROR',str(error),flush=True)
        record['seconds']=round(perf_counter()-start,2)
        records.append(record)
        (ROOT/args.output).write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
