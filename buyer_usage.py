"""Shared, bounded English driving-use vocabulary for chat and explicit forms.

These rules standardize stated uses; they do not infer comfort, safety, vehicle
specifications or market facts. Ambiguous words such as 'travel' need a choice.
"""
import re

USAGES = {'City commuting': 'city_commute', 'Family travel': 'family_travel',
          'Long-distance driving': 'long_distance'}
USAGE_HELP = 'Choose City commuting, Family travel or Long-distance driving; more than one is allowed.'


def normalized_phrase(value):
    """Ignore case, surrounding whitespace and spelling separators only."""
    return re.sub(r'[-_\s]+', ' ', value.strip().casefold())


ALIASES = {}
for label, phrases in {
    'city_commute': ('city commute', 'city commuting', 'commute', 'commuting',
                     'daily commute', 'daily commuting', 'urban commute', 'urban commuting', 'work commute'),
    'family_travel': ('family travel', 'family trip', 'family trips', 'family outing', 'family outings'),
    'long_distance': ('long distance', 'long distance travel', 'long distance driving',
                      'long distance drive', 'long distance trip', 'long distance trips',
                      'road trip', 'road trips', 'highway driving', 'intercity travel'),
}.items():
    for phrase in (*phrases, label):
        ALIASES[normalized_phrase(phrase)] = label


def parse_usage_list(value):
    """Parse a complete form/list value atomically; never silently drop a token."""
    parts = value.split(',') if isinstance(value, str) else value
    if not isinstance(parts, list) or not all(isinstance(part, str) for part in parts):
        raise ValueError(USAGE_HELP)
    result = []
    for part in parts:
        phrase = normalized_phrase(part)
        if not phrase:
            continue
        if phrase in ('unknown', 'clear'):
            raise ValueError('Select Unknown by itself to clear uses; do not combine it with a driving use.')
        if phrase in ('travel', 'trip', 'trips'):
            raise ValueError("'" + part.strip() + "' is ambiguous. Choose Family travel or Long-distance driving.")
        if phrase not in ALIASES:
            raise ValueError("Unsupported driving use '" + part.strip() + "'. " + USAGE_HELP)
        label = ALIASES[phrase]
        if label not in result:
            result.append(label)
    if not result:
        raise ValueError('Choose a driving use, or select Unknown to clear confirmed uses.')
    return result


PATTERNS = {
    'city_commute': re.compile(r'\b(?:(?:city|daily|urban|work)[-_\s]+)?commut(?:e|ing)\b', re.I),
    'family_travel': re.compile(r'\bfamily[-_\s]+(?:travel|trips?|outings?)\b', re.I),
    'long_distance': re.compile(r'\b(?:long[-_\s]+distance(?:[-_\s]+(?:driv(?:e|ing)|travel(?:ling|ing)?|trips?))?|road[-_\s]+trips?|highway[-_\s]+driving|intercity[-_\s]+travel)\b', re.I),
}


def usage_mentions(text):
    """Keep each exact source phrase, with local positive/negative/uncertain scope."""
    found = []
    for label, pattern in PATTERNS.items():
        for match in pattern.finditer(text):
            before = re.split(r'[,;.!?\n]|\b(?:but|however)\b', text[:match.start()], flags=re.I)[-1]
            after = re.split(r'[,;.!?\n]|\b(?:but|however)\b', text[match.end():], flags=re.I)[0]
            if re.search(r"\b(?:not sure|unsure|unknown|maybe|might|possibly|whether)\b", before, re.I):
                kind = 'uncertain'
            elif (re.search(r"\b(?:not|no|don't|do not|never|cannot|can't|without|remove|forget|avoid|exclude|instead of)\b", before, re.I)
                  or re.match(r"\s*(?:(?:is|are)\s+)?(?:not needed|not required|no longer needed)\b", after, re.I)):
                kind = 'negative'
            else:
                kind = 'positive'
            found.append({'label': label, 'evidence': match.group(), 'kind': kind, 'start': match.start()})
    return sorted(found, key=lambda item: item['start'])


def explicit_buyer_usages(text):
    """Return affirmative uses, withholding any use contradicted in this message."""
    mentions = usage_mentions(text)
    blocked = {item['label'] for item in mentions if item['kind'] != 'positive'}
    recovered = []
    for item in mentions:
        if item['kind'] == 'positive' and item['label'] not in blocked and item['label'] not in {label for label, _ in recovered}:
            recovered.append((item['label'], item['evidence']))
    return recovered


def ambiguous_buyer_travel(text):
    """Remember a broad travel request without inventing its usage category."""
    known = usage_mentions(text)
    for match in re.finditer(r'\b(?:travel|trips?)\b', text, re.I):
        if any(item['start'] <= match.start() < item['start'] + len(item['evidence']) for item in known):
            continue
        before = re.split(r'[,;.!?\n]', text[:match.start()])[-1]
        after = text[match.end():]
        if (re.search(r"\b(?:not|no|don't|do not|without|remove|forget|avoid|unknown|unsure)\b", before, re.I)
                or re.match(r'\s+together\b', after, re.I)):
            continue
        return match.group()
    return None


def usage_replacement_requested(text):
    """An unrelated 'only Toyota' or 'replace my budget' is not a usage reset."""
    for item in usage_mentions(text):
        if item['kind'] != 'positive':
            continue
        before = re.split(r'[,;.!?\n]', text[:item['start']])[-1]
        end = item['start'] + len(item['evidence'])
        after = re.split(r'[,;.!?\n]', text[end:])[0]
        if (re.search(r'\breplace\b.{0,35}\b(?:driving use|uses|usage)\b', before, re.I)
                or re.search(r'\bonly\s+(?:(?:use|need|want|do|for|drive|it|a car|the car)\s+){0,4}$', before, re.I)
                or re.match(r'\s+instead(?:\s+of)?\b', after, re.I)):
            return True
    return False


def ground_usage_update(value, evidence, operation, previous=()):
    """Even a valid enum needs matching source words; model labels are not proof."""
    if value == [] and re.search(r'\b(?:clear|unknown|remove|forget|no preference)\b', evidence, re.I):
        return []
    supplied = parse_usage_list(value)
    mentions = usage_mentions(evidence)
    supported = {item['label'] for item in mentions if item['kind'] == 'positive' or operation == 'remove' and item['kind'] == 'negative'}
    # Small models sometimes copy old list members into a current-turn patch.
    # Ignore such duplicates; they are not newly supported facts and must not
    # invalidate the genuinely new use or erase already confirmed memory.
    if not (set(supplied) - supported) <= set(previous):
        raise ValueError('The proposed driving use does not match the stated words. ' + USAGE_HELP)
    return [label for label in supplied if label in supported]
