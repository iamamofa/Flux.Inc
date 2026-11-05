"""Aggregate recorded inventory origins using local geographical references."""
from collections import Counter
from functools import lru_cache
import json
import math
from pathlib import Path
import re
import unicodedata

DATA_PATH = Path(__file__).resolve().parent.parent / 'static' / 'data'
WEST_AFRICA_CODES = frozenset({'BEN', 'BFA', 'CPV', 'CIV', 'GMB', 'GHA', 'GIN', 'GNB', 'LBR', 'MLI', 'MRT', 'NER', 'NGA', 'SEN', 'SLE', 'TGO'})
ALIASES = {'ivory coast': 'CIV', 'cote divoire': 'CIV', 'cape verde': 'CPV', 'the gambia': 'GMB', 'republic of ghana': 'GHA', 'dr congo': 'COD', 'drc': 'COD', 'republic of congo': 'COG', 'united republic of tanzania': 'TZA', 'swaziland': 'SWZ', 'usa': 'USA', 'u s a': 'USA', 'united states of america': 'USA', 'uk': 'GBR', 'u k': 'GBR', 'great britain': 'GBR', 'england': 'GBR', 'south korea': 'KOR', 'north korea': 'PRK', 'russian federation': 'RUS', 'viet nam': 'VNM', 'czech republic': 'CZE', 'turkiye': 'TUR', 'uae': 'ARE'}
ALIASES.update({
    'democratic republic of congo': 'COD',
    'congo kinshasa': 'COD',
    'congo brazzaville': 'COG',
})


def _normalized(value):
    value = unicodedata.normalize('NFKD', str(value or ''))
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', value.casefold()).strip()


def _text(value):
    return str(value or '').strip()


@lru_cache(maxsize=1)
def _country_reference():
    records = json.loads((DATA_PATH / 'countries.json').read_text(encoding='utf-8'))
    countries, aliases = {}, {}
    for record in records:
        code = record['iso_a3']
        countries[code] = record
        for value in (record['name'], code, record.get('iso_a2', ''), *record.get('aliases', [])):
            if value:
                aliases[_normalized(value)] = code
    aliases.update({alias: code for alias, code in ALIASES.items() if code in countries})
    text_aliases = sorted(((alias, code) for alias, code in aliases.items() if len(alias) > 2), key=lambda pair: -len(pair[0]))
    return countries, aliases, text_aliases


@lru_cache(maxsize=1)
def _ghana_places():
    records = json.loads((DATA_PATH / 'ghana_locations.json').read_text(encoding='utf-8'))
    return {_normalized(name): place for place in records for name in (place['name'], *place.get('aliases', []))}


def normalize_country(value):
    """Resolve exact country names and ISO codes to alpha-3 codes."""
    return _country_reference()[1].get(_normalized(value))


def _country_in_text(value):
    normalized = _normalized(value)
    if not normalized:
        return None
    exact = normalize_country(value)
    if exact:
        return exact
    remaining, matches = f' {normalized} ', set()
    for alias, code in _country_reference()[2]:
        phrase = f' {alias} '
        if phrase in remaining:
            matches.add(code)
            remaining = remaining.replace(phrase, ' ')
    return next(iter(matches)) if len(matches) == 1 else None


def _metadata(item):
    raw = getattr(item, 'metadata', {})
    if not isinstance(raw, dict):
        return {}
    return {_normalized(k): _text(v) for k, v in raw.items() if isinstance(v, str)}


def _first(metadata, names):
    for name in names:
        if metadata.get(name):
            return metadata[name], f'Metadata: {name}'
    return '', ''


ORIGIN_KEYS = ('country of origin', 'origin country', 'collection country', 'sampling country', 'sample origin country', 'sample country', 'country of collection')
CITY_KEYS = ('origin city', 'collection city', 'sampling city', 'sample city', 'city', 'town')
REGION_KEYS = ('origin region', 'collection region', 'sampling region', 'region', 'province', 'district')
SITE_KEYS = ('collection site', 'sampling site', 'origin site', 'sample site', 'site', 'locality', 'geographic location')


def _coordinate_pair(latitude, longitude):
    try:
        latitude, longitude = float(latitude), float(longitude)
    except (TypeError, ValueError, OverflowError):
        return None
    if math.isfinite(latitude) and math.isfinite(longitude) and -90 <= latitude <= 90 and -180 <= longitude <= 180:
        return latitude, longitude
    return None


def _ghana_city(*values):
    for value in values:
        for candidate in (_text(value), _text(value).split(',')[0]):
            place = _ghana_places().get(_normalized(candidate))
            if place:
                return place
    return None


def _sample_coordinates(metadata):
    pairs = (
        (('collection latitude',), ('collection longitude',)),
        (('sampling latitude',), ('sampling longitude',)),
        (('origin latitude',), ('origin longitude',)),
        (('gps latitude', 'gps lat'), ('gps longitude', 'gps lon', 'gps lng')),
        (('latitude', 'lat', 'latitude decimal degrees'), ('longitude', 'lon', 'lng', 'longitude decimal degrees')),
    )
    for lat_keys, lon_keys in pairs:
        latitude, _ = _first(metadata, lat_keys)
        longitude, _ = _first(metadata, lon_keys)
        pair = _coordinate_pair(latitude, longitude)
        if pair:
            return pair, 'Metadata coordinates'
    for key in ('gps coordinates', 'collection coordinates', 'sampling coordinates', 'coordinates', 'gps'):
        components = re.split(r'[,;\s]+', metadata.get(key, '').strip(' []()'))
        if len(components) == 2:
            pair = _coordinate_pair(*components)
            if pair:
                return pair, f'Metadata: {key} (latitude, longitude)'
    return None, ''


def _sample_origin(item):
    metadata = _metadata(item)
    city, _ = _first(metadata, CITY_KEYS)
    region, _ = _first(metadata, REGION_KEYS)
    site, _ = _first(metadata, SITE_KEYS)
    origin_country, origin_source = _first(metadata, ORIGIN_KEYS)
    generic_country, generic_source = _first(metadata, ('country',))
    country, source = None, ''
    for candidate, candidate_source in (
        (origin_country, origin_source),
        (_text(getattr(item, 'country', '')), 'Sample country'),
        (generic_country, generic_source),
        (city, 'Country in metadata city'),
        (region, 'Country in metadata region'),
        (site, 'Country in metadata collection site'),
    ):
        country = _country_in_text(candidate)
        if country:
            source = candidate_source
            break
    place = _ghana_city(city, site) if country in (None, 'GHA') else None
    if place and not country:
        country, source = 'GHA', 'Recognized Ghana city in sample metadata'
    coordinates, coordinate_source = _sample_coordinates(metadata)
    warning = ''
    if coordinates:
        coordinate_country = _coordinate_country(coordinates)
        if not country:
            country = coordinate_country
            if country:
                coordinate_source += ' / country from Africa boundary'
        else:
            reference = _country_reference()[0][country]
            if ((coordinate_country and coordinate_country != country)
                    or (reference['continent'] == 'Africa' and coordinate_country != country)):
                warning = 'Coordinates fall outside the recorded country boundary; country-level origin shown.'
                coordinates, place = None, None
    parts = list(dict.fromkeys(v for v in (site, city, region) if v))
    return {
        'country_code': country, 'location': ', '.join(parts),
        'coordinates': coordinates, 'place': place,
        'source': coordinate_source if coordinates else 'Natural Earth city reference' if place else source,
        'warning': warning,
        'vendor': '', 'raw_country': origin_country or _text(getattr(item, 'country', '')) or generic_country,
    }


def _vendor_origin(item, kind):
    vendor = _text(getattr(item, 'vendor', ''))
    if kind == 'equipment':
        vendor = _text(getattr(item, 'source', '')) or _text(getattr(item, 'donated_by', ''))
    country_value = _text(getattr(item, 'vendor_country', ''))
    city = _text(getattr(item, 'vendor_city', ''))
    country, source = None, ''
    for candidate, candidate_source in (
        (country_value, 'Vendor country'), (city, 'Country in vendor city'),
        (vendor, 'Country in vendor / equipment source'),
    ):
        country = (_vendor_text_country(candidate) if candidate_source == 'Country in vendor / equipment source'
                   else _country_in_text(candidate))
        if country:
            source = candidate_source
            break
    place = _ghana_city(city, vendor) if country in (None, 'GHA') else None
    if place and not country:
        country, source = 'GHA', 'Recognized Ghana vendor city'
    return {'country_code': country, 'location': city, 'coordinates': None,
            'place': place, 'source': 'Natural Earth city reference' if place else source,
            'vendor': vendor, 'raw_country': country_value}


def build_dashboard_geography(items, kind):
    """Count project-scoped active records by recorded origin, never by quantity.

    Recognized Ghana cities use sourced representative city points; other known
    countries use representative country points. Recorded GPS pairs stay distinct.
    """
    if kind not in {'samples', 'consumables', 'reagents', 'equipment'}:
        raise ValueError('Unknown inventory geography kind.')
    references, _, _ = _country_reference()
    country_counts, location_counts, unmapped_counts = Counter(), {}, Counter()
    total = mapped = 0
    for item in items:
        total += 1
        origin = _sample_origin(item) if kind == 'samples' else _vendor_origin(item, kind)
        code = origin['country_code']
        country = references.get(code)
        coordinates, place = origin['coordinates'], origin['place']
        if not country:
            label = origin['raw_country'] or origin['location'] or origin['vendor'] or 'Location not provided'
            reason = ('Country required for coordinates outside mapped Africa boundaries' if coordinates
                      else 'Country not recognized' if origin['raw_country']
                      else 'Origin location missing or not recognized')
            unmapped_counts[(label, reason)] += 1
            continue
        mapped += 1
        country_counts[code] += 1
        precision = 'coordinates' if coordinates else 'city' if place else 'country'
        latitude, longitude = coordinates if coordinates else (place['latitude'], place['longitude']) if place else (country['latitude'], country['longitude'])
        country_name = country['name']
        label = f"{origin['location']}, {country_name}" if origin['location'] else country_name
        key = (code, label, precision, latitude, longitude, origin.get('warning', ''))
        if key not in location_counts:
            location_counts[key] = {
                'label': label, 'country_code': code, 'country': country_name,
                'latitude': latitude, 'longitude': longitude, 'count': 0,
                'precision': precision, 'source': origin['source'], 'vendors': set(),
                'warning': origin.get('warning', ''),
            }
        location_counts[key]['count'] += 1
        if origin['vendor']:
            location_counts[key]['vendors'].add(origin['vendor'])
    countries = []
    for code, count in sorted(country_counts.items(), key=lambda pair: (-pair[1], references[pair[0]]['name'])):
        country = references[code]
        region = 'West Africa' if code in WEST_AFRICA_CODES else 'Africa' if country['continent'] == 'Africa' else 'Outside Africa'
        countries.append({'code': code, 'name': country['name'], 'count': count, 'region': region,
                          'latitude': country['latitude'], 'longitude': country['longitude']})
    locations = sorted(location_counts.values(), key=lambda point: (-point['count'], point['label']))
    for location in locations:
        location['vendors'] = sorted(location['vendors'], key=str.casefold)
    samples = kind == 'samples'
    return {
        'kind': kind, 'title': 'Where samples come from' if samples else 'Where vendors deliver from',
        'description': 'Explore collection locations across Ghana, West Africa and beyond.' if samples else 'Explore the countries and cities supplying your project.',
        'summary': {
            'total': total, 'mapped': mapped, 'unmapped': total - mapped, 'countries': len(countries),
            'ghana': country_counts['GHA'],
            'west_africa': sum(n for c, n in country_counts.items() if c in WEST_AFRICA_CODES),
            'outside_africa': sum(n for c, n in country_counts.items() if references[c]['continent'] != 'Africa'),
            'coordinate_conflicts': sum(point['count'] for point in locations if point['warning']),
        },
        'countries': countries, 'locations': locations,
        'location_warnings': [
            {'label': point['label'], 'count': point['count'], 'reason': point['warning']}
            for point in locations if point['warning']
        ],
        'unmapped_locations': [
            {'label': label, 'count': count, 'reason': reason}
            for (label, reason), count in sorted(unmapped_counts.items(), key=lambda pair: (-pair[1], pair[0][0]))
        ],
        'default_view': 'west-africa',
        'source_note': 'Coordinates consistent with recorded African countries are plotted as supplied. Conflicting coordinates fall back to country-level origins. Recognized Ghana cities use approximate city points.',
    }


@lru_cache(maxsize=1)
def _africa_features():
    features = json.loads((DATA_PATH / 'africa.geojson').read_text(encoding='utf-8'))['features']
    polygons = []
    for feature in features:
        geometry = feature['geometry']
        parts = geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else [geometry['coordinates']]
        for polygon in parts:
            longitudes, latitudes = zip(*polygon[0])
            bounds = (min(longitudes), min(latitudes), max(longitudes), max(latitudes))
            polygons.append((feature['properties']['iso_a3'], bounds, polygon))
    return polygons


def _in_ring(longitude, latitude, ring):
    inside = False
    previous_x, previous_y = ring[-1]
    for current_x, current_y in ring:
        if (current_y > latitude) != (previous_y > latitude):
            intersection = (previous_x - current_x) * (latitude - current_y) / (previous_y - current_y) + current_x
            if longitude < intersection:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def _coordinate_country(coordinates):
    """Assign GPS-only African origins using local country boundaries."""
    latitude, longitude = coordinates
    for code, (west, south, east, north), polygon in _africa_features():
        if west <= longitude <= east and south <= latitude <= north:
            if _in_ring(longitude, latitude, polygon[0]) and not any(_in_ring(longitude, latitude, hole) for hole in polygon[1:]):
                return code
    return None


def _vendor_text_country(value):
    """Only an explicit country or delimited address segment implies origin."""
    matches = set()
    for segment in re.split(r'[,;|()\n]', _text(value)):
        normalized = _normalized(segment)
        if len(normalized) > 2 or normalized == 'uk':
            country = normalize_country(segment)
            if country:
                matches.add(country)
    return next(iter(matches)) if len(matches) == 1 else None
