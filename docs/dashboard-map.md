# Inventory origin map

The map is the main graphic on the Samples, Consumables, Reagents and Equipment
dashboards. It starts in West Africa, with Ghana highlighted. Use **Ghana**,
**West Africa**, **Africa** or **World** to change the view. Select a country or location to
see its counts and recorded locations. Stock, availability and expiry charts
appear below the map.

Use the zoom controls to inspect a selected area and **Reset view** to return to
the chosen regional view. The small Africa overview keeps the current area in
context. City callouts show recorded origin counts, and the ranked country list
shows each country's share of mapped records.

The original atlas design and dashboard layout are preserved. Colours follow
the Flux design system: orange accents, white cards, and neutral grey and
charcoal map surfaces. A few explorer features take inspiration from
[WFP HungerMap](https://hungermap.wfp.org/food?w=ipc-phase-3&m=percentage): country
search, **Records** / **% Share** controls, and an optional World view. Percentages
are each country's share of mapped inventory records. Search also finds
international countries without records, which display zero. World boundaries
load when needed. Use the expand control for a full-screen map where supported.

Counts represent active inventory records in the current project, rather than
packs, equipment quantities, sample volumes or delivery transactions. Project
membership is required to view the dashboard.

## Sample origins

The map reads the sample's existing **Country** field and custom metadata. Names
are matched without regard to capitalization, spaces, underscores or accents.
Country names and ISO codes such as Ghana, GH and GHA are grouped together.

| Metadata | Recognized names (examples) |
| --- | --- |
| Country | Country of origin, Origin country, Collection country, Sampling country, Country |
| City | Collection city, Origin city, Sampling city, City, Town |
| Region | Collection region, Origin region, Region, Province, District |
| Site | Collection site, Sampling site, Site, Locality, Geographic location |
| Coordinates | Latitude + Longitude; Collection latitude + Collection longitude; GPS latitude + GPS longitude; GPS coordinates |

Explicit origin-country metadata takes precedence over the sample Country
field. Generic metadata Country is a fallback. Coordinate strings use
**latitude, longitude** order in decimal degrees. Valid coordinate pairs without
a country can be matched against the local Africa boundaries. Coordinates
outside those boundaries require a country to be entered.

Coordinates that disagree with a recorded African country are flagged for
review. The record retains its entered country and uses country-level shading,
so a conflicting point cannot appear inside a neighbouring country.

Recognized Ghana cities use approximate city centres from Natural Earth.
Other location names remain visible in the details but use country-level
shading unless coordinates are supplied. Regions and sites are never treated as
exact collection addresses. Storage metadata does not determine sample origin.

## Vendor delivery origins

Use **Vendor delivery country** and **Vendor delivery city** in the inventory
Add/Edit forms. Equipment also has **Vendor / delivery source**; its existing
Donated By field is used when no source is entered. Reagent country of manufacture
and laboratory storage locations do not determine the vendor's delivery origin.

Existing vendor/source text can supply an origin when it contains an explicit
country segment, for example `Supplier (Accra, Ghana)`. A supplier's brand name
alone does not imply a location. Vendors outside Africa remain in the country
list, with an Outside Africa label and their recorded location details.

The new vendor location fields are optional. Existing records without usable
origins are counted under **records needing location details**. Expand that
section to review them. Vendor origins are included in inventory exports and
retained in archived records and restoration.

## Setup and data sources

Apply the additive migration before running the updated application:

```sh
python manage.py migrate
```

The map uses local GeoJSON converted from Natural Earth shapefiles, with no map
API key, external map tiles or external geocoding requests. Source details,
license and rebuild instructions are in [static/data/README.md](../static/data/README.md).
Production installations should collect static files after updating the code.
