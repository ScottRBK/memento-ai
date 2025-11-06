# Forgetful - AI Memory Service


## Features

## Feature Roadmap (in order of priority)
- [ ] Dynamic Tool Discovery 
- [ ] Resources 
    - Project 
    - Documents
    - Code Artifacts
- [ ] Search Enhancements
    - Implement Cross-Encoder reranking
- [ ] Authentication 
    - Implement Opaque Bearer Token authorisation support
    - Implement Authorisation Code flow support
- [ ] Repository Adapters
    - Add SQLLite repository support


---
# Getting Started

## Running Locally Without Auth
The easiest way to get going without authentication in place then perform the following steps:

copy the environments file 

```bash
cp docker/.env.example docker/.env.development
```
Once the file is copied you can then start making changes to it to add in your own 
details against the default user and any preferences around ports and repository configuration

Then simply run and pass in the appropriate environment variable

```bash
cd docker && ENVIRONMENT=development docker compose up -d
```
---
## Search

For more information on configuring Forgetful's search capabilities and how it works under the hood see
[Search](docs/search.md) for details
---
## Contributing

See [Contributors](docs/contributors.md) for details
--- 
## Licence

MIT License - see [LICENCE](LICENCE.md) for details



