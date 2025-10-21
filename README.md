# Memento AI Memory Service


## Features

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
## Contributing
See [Contributors](docs/contributors.md) for details
--- 
## Licence

MIT License - see [LICENCE](LICENCE.md) for details



