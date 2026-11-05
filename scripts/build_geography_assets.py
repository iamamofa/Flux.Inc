"""Rebuild the dashboard's public-domain Natural Earth geography assets.

Build-time only: install pyshp, then run this script from any directory.
The Django application and browser do not need pyshp or network access.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
from urllib.request import urlopen
from zipfile import ZipFile

import shapefile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'static' / 'data'
COUNTRIES_URL = 'https://naturalearth.s3.amazonaws.com/50m_cultural/ne_50m_admin_0_countries.zip'
PLACES_URL = 'https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_populated_places_simple.zip'


def reader(url, name):
    raw = urlopen(url, timeout=60).read()
    archive = ZipFile(io.BytesIO(raw))
    print(f'{name}: sha256 {hashlib.sha256(raw).hexdigest()}')
    return shapefile.Reader(**{
        ext: io.BytesIO(archive.read(f'{name}.{ext}'))
        for ext in ('shp', 'shx', 'dbf')
    })


def aliases(record):
    # Preserve alternative labels supplied by Natural Earth; application-specific
    # common abbreviations are normalized by the backend rather than guessed here.
    fields = ('NAME', 'NAME_LONG', 'NAME_EN', 'NAME_SORT', 'NAME_ALT', 'BRK_NAME', 'NAME_CIAWF')
    return sorted({str(record[field]).strip() for field in fields
                   if record.get(field) and str(record[field]).strip() != '-99'})


def properties(record):
    iso_a3 = record['ISO_A3']
    if iso_a3 == '-99':
        iso_a3 = record['ADM0_A3']
    iso_a2 = record['ISO_A2']
    if iso_a2 == '-99':
        iso_a2 = record['ISO_A2_EH'] if iso_a3 in ('FRA', 'NOR', 'KOS') else ''
    return {
        'iso_a3': iso_a3,
        'iso_a2': iso_a2,
        'name': record.get('NAME_EN') or record['NAME_LONG'],
        'longitude': round(record['LABEL_X'], 5),
        'latitude': round(record['LABEL_Y'], 5),
        'continent': 'Africa' if iso_a3 in ('SYC', 'MUS', 'SHN') else record['CONTINENT'],
        'region': record['SUBREGION'],
        'aliases': aliases(record),
    }


def rounded(coordinates):
    if isinstance(coordinates[0], (float, int)):
        return [round(value, 4) for value in coordinates]
    return [rounded(part) for part in coordinates]


def write(name, value):
    target = OUTPUT / name
    target.write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    print(f'{target.relative_to(ROOT)}: {target.stat().st_size:,} bytes')


def main(world_only=False):
    OUTPUT.mkdir(parents=True, exist_ok=True)
    countries = reader(COUNTRIES_URL, 'ne_50m_admin_0_countries')
    references = []
    features = []
    world_features = []
    for entry in countries.iterShapeRecords():
        record = entry.record.as_dict()
        props = properties(record)
        references.append(props)
        include_africa = record['CONTINENT'] == 'Africa' or props['iso_a3'] in ('SYC', 'MUS', 'SHN')
        include_world = props['iso_a3'] != 'ATA'
        if include_africa or include_world:
            geometry = dict(entry.shape.__geo_interface__)
            geometry['coordinates'] = rounded(geometry['coordinates'])
            feature = {'type': 'Feature', 'properties': props, 'geometry': geometry}
            if include_world:
                world_features.append(feature)
        # Include the mainland and all African sovereign island countries.
        # Remote Antarctic/subantarctic territories are outside this view.
        if include_africa:
            features.append(feature)
    assert len({f['properties']['iso_a3'] for f in world_features}) == len(world_features)
    assert {'GHA', 'DEU', 'CHN', 'GBR', 'USA'} <= {f['properties']['iso_a3'] for f in world_features}
    write('world.geojson', {'type': 'FeatureCollection', 'features': world_features})
    if world_only:
        return
    write('countries.json', sorted(references, key=lambda item: item['name']))
    write('africa.geojson', {'type': 'FeatureCollection', 'features': features})
    places = reader(PLACES_URL, 'ne_10m_populated_places_simple')
    locations = []
    for record in places.iterRecords():
        item = record.as_dict()
        if item['adm0_a3'] != 'GHA':
            continue
        names = {item.get(field, '').strip() for field in ('name', 'nameascii', 'namealt', 'namepar')}
        locations.append({
            'name': item['name'],
            'latitude': round(item['latitude'], 6),
            'longitude': round(item['longitude'], 6),
            'precision': 'city',
            'aliases': sorted(names - {'', item['name']}),
        })
    write('ghana_locations.json', sorted(locations, key=lambda item: item['name']))
    assert len({item['iso_a3'] for item in references}) == len(references)
    assert {'GHA', 'NGA', 'CIV', 'CPV', 'SYC', 'MUS', 'STP', 'COM'} <= {f['properties']['iso_a3'] for f in features}
    assert {'Accra', 'Kumasi', 'Tamale', 'Cape Coast'} <= {p['name'] for p in locations}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--world-only', action='store_true', help='Only regenerate world.geojson; preserve the other local assets.')
    main(world_only=parser.parse_args().world_only)
