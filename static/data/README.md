# Dashboard geography

These are local, public-domain reference assets. They contain no inventory or
sample records. Dashboard rendering and location matching work without external
map tiles, network geocoding, or a geography service.

- `africa.geojson`: Natural Earth 1:50m Admin 0 countries, version 5.1.1,
  converted directly from the `.shp`/`.dbf` files to GeoJSON. Includes the African
  mainland, African sovereign island countries, Western Sahara, Somaliland, and
  Saint Helena. Coordinates are WGS84 longitude/latitude, rounded to four decimal
  places. Shapes retain Natural Earth's default boundaries.
- `world.geojson`: worldwide country/territory boundaries from the same
  Natural Earth 1:50m shapefile, with Antarctica omitted. It supports the
  optional World view and supplier countries outside Africa. Properties and
  WGS84 coordinate precision match `africa.geojson`; mainland and overseas
  polygon parts are retained. This larger asset is loaded only when the World
  view is used, so it does not add a required map service or runtime dependency.
- `countries.json`: worldwide country/territory names, alternative labels, ISO
  identifiers and representative label coordinates from the same shapefile.
  The `region` field is Natural Earth's `SUBREGION`. Entries without an ISO A3
  code use Natural Earth's `ADM0_A3` identifier; unavailable ISO A2 values are
  empty strings. Label coordinates support country-level map markers; they are
  not collection or vendor addresses.
- `ghana_locations.json`: 17 named Ghana cities and representative coordinates
  from Natural Earth's 1:10m Populated Places Simple shapefile. These points
  identify cities, not specific facilities, sample collection sites, or exact
  vendor premises. Historical administrative-region labels from the source
  were deliberately omitted.

## Sources and license

Made with [Natural Earth](https://www.naturalearthdata.com/).
Natural Earth map data is [public domain](https://www.naturalearthdata.com/about/terms-of-use/).

Country dataset:
[Admin 0 – Countries, 1:50m](https://www.naturalearthdata.com/downloads/50m-cultural-vectors/50m-admin-0-countries-2/).
Original shapefile archive:
<https://naturalearth.s3.amazonaws.com/50m_cultural/ne_50m_admin_0_countries.zip>.
SHA-256 of the archive used:
`5fed433373581fa648920435f937d95f2d3c0200e067409c6478dcdf1b853139`.

City dataset:
[1:10m cultural vectors](https://www.naturalearthdata.com/downloads/10m-cultural-vectors/).
Original shapefile archive:
<https://naturalearth.s3.amazonaws.com/10m_cultural/ne_10m_populated_places_simple.zip>.
SHA-256 of the archive used:
`2963ee08f7743f13f37d5243acd77a2f7a510e26a36c7e04b920f1b381f2b251`.

Retrieved 4 November 2026. The small African island countries present at 1:50m
are a reason to use this scale rather than the coarser 1:110m product.

## Rebuild

The assets are already vendored. Rebuilding is optional and requires network
access plus `pyshp` as a build-time dependency only:

```sh
python -m pip install pyshp
python scripts/build_geography_assets.py
```

The rebuild script prints source archive hashes, creates the four assets, and
checks unique country identifiers and required Ghana/West Africa/island entries.
To regenerate only the World boundaries while preserving the other assets:

```sh
python scripts/build_geography_assets.py --world-only
```
