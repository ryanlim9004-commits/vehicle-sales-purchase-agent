"""Conservative source-text checks after LLM extraction, before any business tool.

These guards cover explicit numeric/unit forms; they are not a full English parser.
Unsupported or conflicting expressions are clarified rather than guessed.
"""
# Learning guide:
# Check the original wording after single-turn model extraction.
# Regexes support bounded English number, unit, currency and history forms.
# Return unknown plus a question when evidence is missing, conflicting or unsupported.
import re
from decimal import Decimal
from buyer_usage import explicit_buyer_usages

# Regex named groups preserve the written number together with its unit or
# currency. Decimal conversion happens only after the surrounding role is checked.
DIGITS = r'[+-]?(?:\d{1,3}(?:,\d{3})+|\d{1,3}(?: \d{3})+|\d+)(?:\.\d+)?'
WORDS = r'(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million)'
NUMBER = rf'(?:{DIGITS}\s*[kK]?|{WORDS}(?:[\s-]+(?:and\s+)?{WORDS})*)'
DISTANCE = re.compile(rf'(?<![\w.,/])(?P<number>{NUMBER})\s*(?P<unit>kilometres?|kilometers?|kms?|metres?|meters?|miles?|mi|m)\b', re.I)
CURRENCY = r'(?:MYR|RM|USD|SGD|AUD|EUR|GBP|\$|\u00a3|\u20ac)'
MONEY = re.compile(rf'(?<![A-Za-z])(?P<currency>{CURRENCY})\s*(?P<number>{NUMBER})(?!\w|[.,]\d)|(?<![\w.,])(?P<suffix_number>{NUMBER})\s*(?P<suffix_currency>MYR|RM|ringgit|USD|SGD|AUD|EUR|GBP)\b',re.I)
UNITS = dict(zip('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen'.split(),range(20)))
UNITS.update(dict(zip('twenty thirty forty fifty sixty seventy eighty ninety'.split(),range(20,100,10))))


# Parse supported digit, k-suffix or English-number forms into Decimal, without guessing unknown
# words.
def number_value(raw):
    raw = raw.strip().lower()
    if re.fullmatch(rf'{DIGITS}\s*k?',raw):
        scaled = raw.endswith('k')
        return Decimal(raw.rstrip('k').strip().replace(',','').replace(' ','')) * (1000 if scaled else 1)
    current = total = 0
    for word in re.split(r'[\s-]+',raw):
        if word == 'and':
            continue
        if word in UNITS:
            current += UNITS[word]
        elif word == 'hundred':
            current = (current or 1)*100
        elif word in ('thousand','million'):
            total += (current or 1) * (1000 if word == 'thousand' else 1000000)
            current = 0
        else:
            raise ValueError('Unsupported number expression.')
    return Decimal(total+current)


# Read a bounded preceding clause so unit/currency guards can distinguish an amount from nearby
# context.
def clause_before(text, start):
    return re.split(r'[,;.!?\n]',text[max(0,start-80):start])[-1]


# Read a bounded following clause to detect daily distances, instalments and other context markers.
def clause_after(text, end):
    return re.split(r'[,;.!?\n]',text[end:end+65])[0]


# Return (kilometres, evidence notes, issue); only one supported exact odometer reading is accepted.
def mileage_from_text(text):
    values, evidence = [], []
    for match in DISTANCE.finditer(text):
        before, after = clause_before(text,match.start()), clause_after(text,match.end())
        if re.search(rf'{CURRENCY}\s*$',before,re.I):
            continue
        labelled = bool(re.search(r'\b(mileage|odometer|odo|miles? on (?:the )?clock)\b',before,re.I))
        if re.match(r'\s*(?:/\s*(?:day|week)|per day|per week|daily)',after,re.I):
            continue
        if not labelled and re.search(r'\b(daily|per day|each day|commute|commuting|trip|per week)\b',before+' '+after,re.I):
            continue
        # A distance range/comparison is not an exact odometer reading.
        prefix = text[max(0,match.start()-30):match.start()]
        if re.search(r'(?:\b(?:under|over|about|around|roughly|circa|nearly|almost|approximately|between|less than|more than|up to|at least)\s*|~\s*|\d\s*[kK]?\s*(?:-|to|and)\s*)$',prefix,re.I):
            return None, [], 'Please provide the exact odometer reading and its unit; a range or approximate limit was supplied.'
        value = number_value(match['number'])
        unit = match['unit'].lower()
        # All stored odometer values use kilometres: m * 0.001; miles *
        # 1.609344. The magnitude must follow the source unit, not an LLM guess.
        factor = Decimal('0.001') if unit in ('m','metre','metres','meter','meters') else Decimal('1.609344') if unit in ('mi','mile','miles') else Decimal(1)
        km = value*factor
        if km < 0 or km > 2000000:
            return None, [], 'Mileage is outside the supported range. Please confirm the odometer reading and unit.'
        values.append(km)
        evidence.append(f"Mileage source '{match.group().strip()}' normalized to {km.normalize():f} km.")
    if not values:
        return None, [], 'Please state the odometer reading with an explicit unit (km, m/metres, or mi/miles); no supported mileage evidence was found.'
    if len(set(values)) != 1:
        return None, evidence, 'Conflicting mileage readings were supplied. Please provide one current odometer reading with its unit.'
    return float(values[0]), evidence, None


# Return a positive total MYR budget, using an explicit range upper bound;
# foreign/monthly/conflicting totals ask again.
def budget_from_text(text):
    # Accept the user's existing compact spelling "budgetRM50000".
    text = re.sub(r'(?i)(budget)(?=RM|MYR)',r'\1 ',text)
    totals, evidence, foreign, spans, explicit_range = [], [], False, [], False
    for match in MONEY.finditer(text):
        currency = (match['currency'] or match['suffix_currency']).upper()
        raw = match['number'] or match['suffix_number']
        before, after = clause_before(text,match.start()), clause_after(text,match.end())
        context = before+' '+after
        if re.search(r'\b(monthly|per month|per week|weekly|instalments?|installments?)\b|/\s*(?:mo|month|week)\b',context,re.I):
            continue
        if currency not in ('RM','MYR','RINGGIT'):
            foreign = True
            continue
        amount = number_value(raw)
        if amount <= 0:
            return None, [], 'Please provide a positive total purchase budget in MYR.'
        totals.append(amount)
        spans.append((match.start(),match.end()))
        evidence.append(f"Budget source '{match.group().strip()}' normalized to MYR {amount.normalize():f}.")
        # A common range with one currency token: RM40k to 50k.
        tail = text[match.end():]
        upper = re.match(rf'\s*(?:-|to)\s*(?!(?:{CURRENCY}))(?P<upper>{NUMBER})(?!\w|[.,]\d)',tail,re.I)
        if upper:
            upper_amount = number_value(upper['upper'])
            if upper_amount < amount:
                return None, evidence, 'Budget range is reversed. Please confirm the maximum total purchase budget in MYR.'
            totals.append(upper_amount)
            explicit_range = True
    if foreign:
        return None, evidence, 'A non-MYR or ambiguous currency was supplied. Please confirm a total purchase budget in MYR; no exchange conversion is performed.'
    if not totals:
        return None, evidence, 'Please specify the total purchase budget with an explicit MYR/RM currency; a monthly payment alone is not a purchase budget.'
    unique = set(totals)
    if len(unique)>1:
        if len(spans)==2:
            connector=text[spans[0][1]:spans[1][0]]
            explicit_range = bool(re.fullmatch(r'\s*(?:to|-)\s*',connector,re.I) or
                                  (re.search(r'\bbetween\s*$',text[:spans[0][0]],re.I) and re.fullmatch(r'\s*and\s*',connector,re.I)))
        if explicit_range and len(totals)==2 and totals[0]<=totals[1]:
            return float(max(totals)), evidence+['Explicit budget range: its upper bound is used.'], None
        return None, evidence, 'Conflicting total budgets were supplied. Please confirm one maximum purchase budget in MYR.'
    return float(totals[0]), evidence, None


# Mask unsupported currency amounts only in the model input; original wording still drives the
# final currency check.
def buyer_extraction_text(text):
    """Keep unrelated facts extractable when the budget uses an unsupported currency.

    Original text is still passed to ground_buyer; no exchange conversion occurs.
    """
    # Keep MYR money text unchanged and substitute a clarification marker for each
    # foreign-currency match.
    def replace(match):
        currency=(match['currency'] or match['suffix_currency']).upper()
        return match.group() if currency in ('MYR','RM','RINGGIT') else '[foreign-currency amount omitted; ask for MYR budget]'
    return MONEY.sub(replace,text)


# Recheck mileage, manufacturing year and damage wording; revalidate the frame and attach source
# notes/questions.
def ground_seller(text, profile):
    data = profile.model_dump()
    # Replace the proposed model mileage with the independently parsed source
    # value, even when the proposed number looked valid to the schema.
    notes = []
    questions = list(profile.clarification_notes)
    mileage, evidence, issue = mileage_from_text(text)
    data['mileage_km'] = mileage
    notes.extend(evidence)
    if issue:
        questions.append(issue)
    else:
        questions=[q for q in questions if not (re.search(r'\b(mileage|odometer|distance|miles|kilometres|kilometers|metres|meters|unit)\b',q,re.I) and not re.search(r'\b(year|condition|variant|brand|accident|flood)\b',q,re.I))]
    years = set(re.findall(r'\b(?:19|20)\d{2}\b',text))
    manufactured = set(re.findall(r'\b(?:manufactured|manufacturing year|year of manufacture|built)(?:\s+(?:in|is))?\s*[:=]?\s*((?:19|20)\d{2})\b',text,re.I))
    registered = set(re.findall(r'\b(?:registered|registration year|registration date)\b[^,.;\n]{0,30}?\b((?:19|20)\d{2})\b',text,re.I))
    if len(manufactured)>1:
        data['year']=None
        questions.append('Conflicting manufacturing years were supplied. Please confirm the manufacturing year.')
    elif len(manufactured)==1:
        data['year']=int(next(iter(manufactured)))
        notes.append('Manufacturing year checked against an explicit manufacturing statement.')
    elif registered and not (years-registered):
        data['year']=None
        questions.append('Only registration-year evidence is available. Please confirm the manufacturing year.')
    elif data['year'] is not None and str(data['year']) not in years-registered:
        data['year']=None
        questions.append('The extracted manufacturing year could not be grounded in the message. Please confirm it.')
    # Unknown or absent history must not turn into an assertion of "no damage".
    for field, subject in [('major_accident_reported',r'(?:major\s+)?accidents?'),('flood_damage_reported',r'flood(?:ing|ed| damage)?')]:
        mentions = list(re.finditer(r'\b'+subject+r'\b',text,re.I))
        if not mentions:
            data[field]=None
            continue
        unknown = any(re.search(r"\b(not sure|unsure|unknown|uncertain|do not know|don't know)\b",clause_before(text,m.start())+' '+clause_after(text,m.end()),re.I) for m in mentions)
        negatives = list(re.finditer(r'\b(?:no|without|never had|free of|not)\s+(?:any\s+)?'+subject+r'\b',text,re.I))
        shared_no = bool(re.search(r'\b(?:no|without)\s+(?:major\s+)?accidents?\s+(?:or|and)\s+flood(?:ing| damage)?\b',text,re.I))
        suffix_free = bool(re.search(r'\b'+subject+r'[- ]free\b',text,re.I))
        if unknown:
            data[field]=None
        elif (shared_no or suffix_free) and len(mentions)==1:
            data[field]=False
        elif negatives:
            # Mixed positive/negative mentions need clarification rather than a false clean history.
            if len(negatives)!=len(mentions):
                data[field]=None
                questions.append('Damage-history statements conflict. Please clarify major-accident/flood history.')
            else:
                data[field]=False
        elif data[field] is False:
            data[field]=None
            questions.append('A negative damage-history claim could not be verified from the message. Please clarify.')
    data['clarification_notes']=list(dict.fromkeys(questions))
    data['input_validation_notes']=notes
    return type(profile).model_validate(data)


# Ground total budget and household travel, conservatively recover explicit seats/use, and keep
# unrelated known facts.
def explicit_priority_clear(evidence, slot):
    """Recognize a named no-preference answer without clearing another slot."""
    names = {'buyer.fuel_priority': 'fuel', 'buyer.space_priority': '(?:space|luggage)',
             'buyer.safety_priority': 'safety', 'buyer.comfort_priority': 'comfort',
             'buyer.reliability_priority': 'reliability'}
    return slot in names and bool(re.search(r'\bno\s+' + names[slot] + r'\s+preference\b', evidence, re.I))


def ground_reference_priority(evidence, field, value, *, pending=False):
    # A generic "high" cannot silently create an unrelated preference.
    patterns = {'safety_priority': r'\b(safety|safe|safer)\b',
                'comfort_priority': r'\b(comfort|comfortable|comfy)\b',
                'reliability_priority': r'\b(reliability|reliable|dependable)\b'}
    if value not in ('high', 'medium', 'low'):
        raise ValueError('State high, medium or low for this priority.')
    text = evidence.casefold()
    if not pending and not re.search(patterns[field], text):
        raise ValueError('Please name the safety, comfort or reliability preference explicitly.')
    levels = re.findall(r'\b(high|medium|low)\b', text)
    if value != 'low' and re.search(r'\b(not|no|unimportant|avoid|without)\b', text):
        raise ValueError('A negated priority needs clarification; it is not a positive preference.')
    if levels and set(levels) != {value}:
        raise ValueError('The stated priority and extracted value conflict; please clarify it separately.')
    if not levels and (value != 'high' or not re.search(r'\b(important|priority|prioriti[sz]e|want|need|prefer|comfortable|reliable|safe|safer|dependable)\b', text) or re.search(r"\b(not|no|unimportant|avoid|without)\b", text)):
        raise ValueError('Please state high, medium or low for this named priority.')
    return value


def ground_buyer(text, profile):
    data=profile.model_dump()
    if re.search(r"\b(not everyone|not all|won't all|will not all)\b.{0,50}\b(travel|ride|together)\b", text, re.I):
        data['household_travels_together']=False
    elif not re.search(r'\b(everyone|all)\b.{0,50}\b(travel|ride|together)\b', text, re.I):
        data['household_travels_together']=None
    amount,evidence,issue=budget_from_text(text)
    data['budget_myr']=amount
    questions=list(profile.clarification_notes)
    for field in ('safety_priority', 'comfort_priority', 'reliability_priority'):
        if data[field] is not None:
            try:
                # Single-turn extraction cannot use another sentence's level.
                pattern = {'safety_priority': r'\b(safety|safe|safer)\b', 'comfort_priority': r'\b(comfort|comfortable|comfy)\b', 'reliability_priority': r'\b(reliability|reliable|dependable)\b'}[field]
                candidates = [c for c in re.split(r'[,;.!?\n]', text) if re.search(pattern, c, re.I)]
                if not candidates:
                    raise ValueError('An unstated evidence preference was omitted.')
                ground_reference_priority(candidates[-1], field, data[field])
            except ValueError as error:
                data[field] = None
                questions.append(str(error))
    if issue:
        questions.append(issue)
    else:
        questions=[q for q in questions if not (re.search(r'\b(budget|monthly|currency|instalment|installment)\b',q,re.I) and not re.search(r'\b(seats|family|usage|brand|space|fuel)\b',q,re.I))]
    # Recover a small set of explicit domain facts if an uncertain budget made the
    # LLM return an otherwise empty profile. Do not override populated LLM slots.
    if data['required_seats'] is None:
        counts=[]
        for match in re.finditer(rf'(?<![\w.,])(?P<count>{NUMBER})\s*-?\s*(?:seats?|seaters?)\b',text,re.I):
            before=clause_before(text,match.start())
            if re.search(r"\b(not|no|don't|do not|at most|up to|under|fewer than|less than|had|previous)\b",before,re.I):
                continue
            count=number_value(match['count'])
            if count==int(count) and 1<=count<=20:
                counts.append(int(count))
        if len(set(counts))==1:
            data['required_seats']=counts[0]
            evidence.append('Recovered an explicit seat-count requirement from the original message.')
    for label, phrase in explicit_buyer_usages(text):
        if label not in data['usage']:
            data['usage'].append(label)
            evidence.append(f'Recovered explicit usage phrase: {phrase}.')
    data['clarification_notes']=list(dict.fromkeys(questions))
    data['input_validation_notes']=evidence
    return type(profile).model_validate(data)
