# Python Service Template


## Features

---

## Testing

Testing is performed using pytest

### Unit 
found under ```/tests/unit```

### Integration

found under ```/tests/integration```

marked with pytest.mark.integration 

skipped (see ```pytest.ini```) and only used in CI/CD

#### Usage

Integration tests are only designed to run as part of the test phase, after the containers have been built in the workflows. 
They are designed to be pointed to a test container and fire integration tests at it.

---
## Deployment

```build.yml``` builds a container on a push or pull_request from or to master

```test.yml``` will spin up two containers, one for the actual app and another for running integration tests
pointed to the actual app container. 

```deploy.yml``` will take the appripriate docker-compose.{environment}.yml and .env.{environment} files
and have a self hosted runner on that environment take these files and deploy the solution.
We use sparse check outs as well so that for deployment we only have the necessary files on the deployment
server. 

### Environment Selection for Deployments
for self hosted runners the environment will match based on the 'label'. So for example when setting up the
self hosted runner for ```staging``` when prompted populate for any additional labels enter ```staging```

---
## Current shithousery 

There is an issue with the ports not being injected into the docker compose files for the testing so these
are relying on the hardcoded values currently.

--- 
## Licence



