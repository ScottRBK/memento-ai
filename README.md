![Banner](/docs/images/hero_banner.png)

# Features

For our roadmap please see [Features Roadmap](docs/features_roadmap.md)
---
# Getting Started

## Running Locally Without Auth
The easiest way to get going without authentication in place then perform the following steps:

```bash
docker compose up -d
```

copy the environments file 

```bash
cp docker/.env.example docker/.env.
```
Once the file is copied you can make any [configuration](docs/configuration.md) you see fit.

```bash
cd docker && ENVIRONMENT=development docker compose up -d
```
### Connecting to Agent
```json
{
  "mcpServers": {
    "forgetful": {
      "type": "http",
      "url": "http://localhost:8020/mcp" 
      }
    }
}
```
**Note** ⚠️: Assumes default server port 8020, but replace with whatever the environment variable you configured for port

For specific application connection guides see [Connectivity Guide](docs/connectivity_guide.md)

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



