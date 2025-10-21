# Contributing to Memento
This section details information around contributing to this repository. 


## Testing

Testing is performed using pytest

### Unit 
found under ```/tests/unit```

As a general rule, unit tests are kept to a minimum, really designed to test complex functions or areas that warrant immediate validation before adding further logic in the chain. 

### Integration

found under ```/tests/integration```

Testing the wiring - these will form the bulk of the tests that are associated with the solution and should capture the vast majority of the logic that you want to validate. 


### End to End Tests

found under ```/tests/test_e2e```

marked with pytest.mark.e2e

Requires actual containers spun up to call routes into the application

skipped by default

#### Usage

End to End tests are designed to run as part of the later validation phase, after the containers have been built in the workflows. 
They expect a fully provisioned environment and will exercise the application end-to-end against running services.

---
## Deployment

```build.yml``` builds a container on a push or pull_request from or to master

```test.yml``` will spin up two containers, one for the actual app and another for running integration tests
pointed to the actual app container. 

```deploy.yml``` will take the appropriate docker-compose.{environment}.yml and .env.{environment} files
and have a self hosted runner on that environment take these files and deploy the solution.
We use sparse check outs as well so that for deployment we only have the necessary files on the deployment
server. 

### Environment Selection for Deployments
for self hosted runners the environment will match based on the 'label'. So for example when setting up the
self hosted runner for ```staging``` when prompted populate for any additional labels enter ```staging```
