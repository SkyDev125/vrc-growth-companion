"""Display-only conversion, using the same unit definitions and fixtures as the website/bot."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import json
from pathlib import Path

GROUPS = json.loads(Path(__file__).with_name('measurement-units.json').read_text(encoding='utf-8'))
SUPERSCRIPT = str.maketrans('-0123456789', '⁻⁰¹²³⁴⁵⁶⁷⁸⁹')


def _plain(number, places):
    with localcontext() as context:
        context.prec = 350
        rounded = number.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    text = format(rounded, ',f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text


def format_number(value):
    amount = Decimal(str(value))
    magnitude = abs(amount)
    if magnitude >= Decimal('1e6') or (magnitude and magnitude < Decimal('.001')):
        exponent = (magnitude.adjusted() // 3) * 3
        mantissa = amount.scaleb(-exponent)
        places = 2 - abs(mantissa).adjusted()
        with localcontext() as context:
            context.prec = 350
            rounded = mantissa.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
        if abs(rounded) >= 1000:
            exponent += 3
            mantissa /= 1000
            places = 2 - abs(mantissa).adjusted()
        return f'{_plain(mantissa, places)} × 10{str(exponent).translate(SUPERSCRIPT)}'
    places = 2 - magnitude.adjusted() if magnitude and magnitude < Decimal('.01') else 2
    return _plain(amount, places)


def format_measurement(value, unit):
    label = str(unit or '')
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return '—'
    if not amount.is_finite():
        return '—'
    if amount:
        for group in GROUPS:
            source = next((u for u in group['units'] if u['unit'] == label), None)
            if source is None and label in group['aliases']:
                alias = group['aliases'][label]
                source = next((u for u in group['units'] if u['unit'] == alias), None) if isinstance(alias, str) else alias
            if source is None:
                continue
            base = amount * Decimal(str(source['factor']))
            target = group['units'][0]
            for candidate in group['units']:
                if abs(base) >= Decimal(str(candidate['factor'])):
                    target = candidate
            amount = base / Decimal(str(target['factor']))
            label = target['unit']
            break
    return f'{format_number(amount)} {label}'.strip()
