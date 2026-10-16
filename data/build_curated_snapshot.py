"""Reproduce hand-reviewed numeric facts; not a scraper or live inventory fetcher."""
# Learning guide:
# Rebuild saved JSON from manually reviewed advertisement facts below.
# Running this script rewrites vehicles_real.json and source_receipts.json.
# It makes no website requests and does not refresh the observation date.
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ALZA = 'https://www.perodua.com.my/our-models/mpv/new-alza'
MYVI = 'https://www.perodua.com.my/our-models/hatchback/myvi'
BEZZA = 'https://www.perodua.com.my/our-models/sedan/bezza'
OLD_ALZA = 'https://www.carlist.my/used-cars/2020-perodua-alza-1-5-se-mpv-warranty-free-super-good-condition-clean-interior-car-paint-glossy-engine-smooth/18923892'
rows = []


# Build one reviewed record, retain point/range mileage and attach only generation-matched
# reference specifications.
def add(key, model, variant, year, price, seats, mileage, url, *, state='listed_snapshot', updated=None, family=None, brand='Perodua', notes=()):
    row = dict(vehicle_id=key, brand=brand, model=model, variant=variant, year=year, currency='MYR', price_myr=price, seats=seats,
               source_kind='listing', price_type='asking', source_reference=url, observed_on='2026-10-15', availability=state,
               source_updated_on=updated, transmission='Automatic', condition=None,
               evidence_notes=['Manually reviewed public page snapshot via web retrieval; stock and prices can change. Seller condition claims are not independent verification.', *notes])
    if isinstance(mileage, tuple):
        row.update(mileage_km=None, mileage_min_km=mileage[0], mileage_max_km=mileage[1])
    else:
        row['mileage_km'] = mileage
    if family == 'old_alza':
        row.update(length_mm=4220, specs_source_reference=OLD_ALZA)
        row['evidence_notes'].append('Length from same 2020 1.5 SE listing specifications. Fuel/boot values not verified; new-generation Alza specifications are not applied.')
    elif family == 'new_alza':
        row.update(fuel_km_per_l=22.0, fuel_basis='MDC_claim', fuel_source_reference=ALZA, boot_litres=137, boot_configuration='all_seats_up', length_mm=4425, specs_source_reference=ALZA)
        row['evidence_notes'].append('Second-generation AV reference specs, not measured used-car performance. 498 L with the third row folded is NOT used for a seven-seat trip.')
    elif family == 'myvi_dcvt':
        row.update(fuel_km_per_l=21.1, fuel_basis='eco_driving_claim', fuel_source_reference=MYVI, boot_litres=277, boot_configuration='all_seats_up', length_mm=3895, specs_source_reference=MYVI, transmission='D-CVT')
        row['evidence_notes'].append('Reference specs for the matched 1.5 D-CVT generation; listing D-CVT checked. Eco-driving claim is not guaranteed real city consumption.')
    elif family in ('bezza_x', 'bezza_av'):
        row.update(fuel_km_per_l=21.0 if family == 'bezza_x' else 22.0, fuel_basis='eco_driving_claim', fuel_source_reference=BEZZA, boot_litres=508, boot_configuration='all_seats_up', length_mm=4170, specs_source_reference=BEZZA)
        row['evidence_notes'].append('Facelift-generation reference specs: X and AV fuel values kept distinct. Eco-driving claims are not harmonized real-world tests.')
    rows.append(row)


# The following calls encode reviewed facts, not data fetched by this script.
# Arguments are ID, model, variant, manufacturing year, MYR asking price, seats,
# point/range mileage in km, and source URL. Keep sold/reserved rows for audit.
add('CL18923892','Alza','1.5 SE',2020,35888,7,(65000,70000),OLD_ALZA,updated='2026-09-21',family='old_alza')
add('CL19122669','Alza','1.5 SE',2020,45000,7,(100000,105000),'https://www.carlist.my/used-cars/2020-perodua-alza-1-5-se-mpv/19122669',updated='2026-09-21',family='old_alza')
add('CL19418670','Alza','1.5 SE',2020,44800,7,(120000,125000),'https://www.carlist.my/used-cars/2020-perodua-alza-1-5-se-mpv/19418670',updated='2026-09-20',family='old_alza')
add('CL18751444','Alza','1.5 AV',2023,64800,7,(25000,30000),'https://www.carlist.my/used-cars/2023-perodua-alza-1-5-av-a-gear-up-bodykit-full-service-perodua-accident-free-under-warranty-perodua-negotiable-tip-top-condition/18751444',updated='2026-04-17',family='new_alza')
add('CL18249652','Alza','1.5 AV',2023,65800,7,(55000,60000),'https://www.carlist.my/used-cars/2023-perodua-alza-1-5-av-mpv-auto-warranty-perodua-2028year-1-owner-free-tinted-otr/18249652',updated='2026-08-07',family='new_alza')
add('CL18624149','Alza','1.5 AV',2023,58888,7,(10000,15000),'https://www.carlist.my/used-cars/2023-perodua-alza-1-5-av-mpv-super-low-mileage-12k-only-under-warranty-perodua-full-service-record-asa-system-camera-360-reverse-camera/18624149',state='sold',family='new_alza',notes=['Page explicitly marked sold; title preserves a former asking price, not a confirmed sale price.'])
add('CL18807978','Alza','1.5 AV',2023,57800,7,(50000,55000),'https://www.carlist.my/used-cars/2023-perodua-alza-1-5-av-mpv-full-service-record-360-camera-acc-blind-spot-monitoring-loan-bank-9-thn-max-loan/18807978',state='sold',family='new_alza',notes=['Page explicitly marked sold; title asking price retained as historical listing data.'])
add('CL18603852','Alza','1.5 AV',2023,61800,None,None,'https://www.carlist.my/used-cars/2023-perodua-alza-1-5-av-mpv-full-service-record-leather-seat-360-cam-rear-aic-cond-3-year-warranty-win-ang-pau-up-to-rm8-888-from-carlist/18603852',state='sold',notes=['Sold page has no usable individual seat/mileage details; do not fill them from a model assumption.'])
add('CL18939959','Myvi','1.5 H',2022,40500,5,(40000,45000),'https://www.carlist.my/used-cars/2022-perodua-myvi-1-5-h-a/18939959',updated='2026-08-11',family='myvi_dcvt')
add('CL18625566','Myvi','1.5 AV',2022,42800,5,(35000,40000),'https://www.carlist.my/used-cars/perodua-myvi-1-5-advance-38501km-mileage-tahun-dibuat-2022-see-to-believe-1-year-warranty/18625566',updated='2026-08-07',family='myvi_dcvt',notes=['Range from structured listing retained; no midpoint is invented.'])
add('CL18902191','Myvi','1.5 AV',2022,44800,5,(80000,85000),'https://www.carlist.my/used-cars/2022-perodua-myvi-1-5-av-hatchback-advanced-service-record-leather-seat-pre-crash/18902191',state='sold',notes=['Sold page; asking price is only preserved in its title. No unverified fuel specification is attached.'])
add('CS_C606800','Bezza','1.3 X',2023,36600,5,50172,'https://www.carsome.my/buy-car/perodua/bezza/2023-perodua-bezza-x-1.3/c606800',family='bezza_x',notes=['Page says Car in Transit and offers Order Now; treated as a listing snapshot, not confirmed delivery availability. Year from listing title; registration month Sep 2023.'])
add('PT_LP63L6X1P7','Bezza','1.3 X',2023,40800,5,65709,'https://paultan.org/used-cars/perodua/bezza/lp63l6x1p7/',updated='2026-08-21',family='bezza_x',notes=['Publisher-hosted classifieds identify Carro inventory; listing evidence, not independent inspection.'])
add('PT_K4EDNMNYPG','Bezza','1.3 AV',2022,40800,5,59492,'https://paultan.org/used-cars/perodua/bezza/k4ednmnypg/',updated='2026-08-17',family='bezza_av')
add('PT_7PRLM3GLPK','Bezza','1.3 AV',2023,42800,5,64512,'https://paultan.org/used-cars/perodua/bezza/7prlm3glpk/',updated='2026-10-07',family='bezza_av')
add('CS_C6RA000','Avanza','1.5 S',2019,73900,None,40477,'https://www.carsome.my/buy-car/toyota/avanza/2019-toyota-avanza-s-1.5/c6ra000',brand='Toyota',state='sold',notes=['Page says sold; seat label is 7 & Above, not an exact integer, so seats stays null. Asking price is not a transaction label. Year from title; registration Jun 2019.'])
add('CS_CBFS600','Avanza','1.5 S',2019,58000,None,53086,'https://www.carsome.my/buy-car/toyota/avanza/2019-toyota-avanza-s-1.5/cbfs600',brand='Toyota',state='reserved',notes=['Page says ordered/booked; excluded from recommendations. Seat label 7 & Above retained as a note, not converted into exact capacity. Year from title; registration May 2019.'])

if __name__ == '__main__':
    (ROOT/'vehicles_real.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
    receipt = {'checked_on':'2026-10-15', 'grain':'one advertisement/inventory record, not a unique VIN-verified vehicle or a transaction',
               'access':'Public detail pages opened using web tools; no dealer contacted and no personal contact information collected.',
               'sources':[{'vehicle_id':r['vehicle_id'],'url':r['source_reference'],'fields':{k:r.get(k) for k in ('brand','model','variant','year','price_myr','price_type','seats','mileage_km','mileage_min_km','mileage_max_km','availability','source_updated_on')},'notes':r['evidence_notes']} for r in rows],
               'specification_sources':[{'url':ALZA,'scope':'second-generation 1.5 AV; 22 km/L MDC claim; 137 L seats up; 4425 mm'}, {'url':MYVI,'scope':'1.5 D-CVT generation; 21.1 km/L eco-driving claim; 277 L; 3895 mm'}, {'url':BEZZA,'scope':'facelift 1.3 X 21 km/L / AV 22 km/L eco-driving; 508 L; 4170 mm'}]}
    (ROOT/'source_receipts.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Saved {len(rows)} reviewed listing records and numeric source receipts.')
