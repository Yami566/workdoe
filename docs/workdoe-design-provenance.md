# Workdoe design provenance

This pass uses original Workdoe copy, layout, CSS, and artwork. It does not copy
source code, interface text, visual assets, characters, logos, or private system
details from Uber, Craigslist, Meta, or any entertainment property.

## Public references reviewed

- Uber Base Web: MIT-licensed responsive design-system implementation.
  https://github.com/uber/baseweb
- Uber H3: Apache-2.0 geospatial indexing project. Workdoe does not add H3 to
  the MVP because rounded location pins and the existing Leaflet map are enough.
  https://github.com/uber/h3
- Uber Engineering's public marketplace and architecture articles: used only
  for high-level context about role clarity, location relevance, and keeping a
  complex system behind a simple product surface.
  https://www.uber.com/us/en/blog/tech-stack-part-one-foundation/
- Craigslist's official open-source page: confirms the projects Craigslist has
  actually released. No Craigslist application code or private backend design
  was used.
  https://www.craigslist.org/about/open_source
- Meta React and Relay: MIT-licensed public projects. Workdoe does not import
  either framework; their public documentation only reinforced predictable UI
  states and keeping data needs close to the view that uses them.
  https://github.com/facebook/react
  https://github.com/facebook/relay
- Facebook Marketplace help and safety pages: public user documentation used
  only to validate the importance of on-platform messaging, profiles, and
  reporting. Marketplace backend code is not presented as open source.
  https://www.facebook.com/help/1889067784738765
- Cloudflare Workers, HTTPS, and HSTS documentation: current public platform
  guidance for the production deployment.
  https://developers.cloudflare.com/workers/best-practices/workers-best-practices/
  https://developers.cloudflare.com/ssl/edge-certificates/additional-options/always-use-https/
  https://developers.cloudflare.com/ssl/edge-certificates/additional-options/http-strict-transport-security/

## SANA interpretation

No authoritative public UX publication matching the exact phrase "SANA UX
development text" was found. To avoid inventing a source, this pass treats the
four qualities named in the brief as the design standard:

- Coherence: one token system, one navigation vocabulary, and consistent
  project rows across roles.
- Adaptivity: map and role controls reflow cleanly from desktop to mobile.
- Simplicity: map, project list, and sign-in remain on the first screen.
- Delight: an original field-scout deer, restrained signal accents, and brief
  area-scan language add character without obscuring the task.

## Original artwork

`workdoe/static/field-doe.webp` is an original generated raster asset. It uses
no names, characters, logos, or visual references from an existing franchise.
The optimized file is 360 pixels on its longest side and is used only in empty
states.
