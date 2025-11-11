"""
E2E test fixtures with Docker Compose orchestration

Spins up real PostgreSQL + forgetful-service containers using docker/.env.example
to validate the actual deployment configuration.
"""
import pytest
import subprocess
import time
import socket
import httpx
import os
import tempfile
import yaml
from pathlib import Path

# Ensure settings loads docker/.env.example
os.environ["ENVIRONMENT"] = "example"
from app.config.settings import settings


def port_in_use(port: int) -> bool:
    """Check if a port is already in use"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return False
        except OSError:
            return True


def wait_for_healthy(container_name: str, timeout: int = 120) -> None:
    """Wait for Docker container to report healthy status"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            result = subprocess.run(
                ["docker", "inspect", "--format={{.State.Health.Status}}", container_name],
                capture_output=True,
                text=True,
                check=True
            )
            status = result.stdout.strip()
            if status == "healthy":
                print(f"✓ {container_name} is healthy")
                return
            elif status == "unhealthy":
                raise RuntimeError(f"Container {container_name} is unhealthy")

            time.sleep(1)
        except subprocess.CalledProcessError:
            time.sleep(1)

    raise TimeoutError(f"Container {container_name} did not become healthy within {timeout}s")


def wait_for_http(url: str, timeout: int = 60) -> None:
    """Wait for HTTP endpoint to respond with 200"""
    start = time.time()
    while time.time() - start < timeout:
        try:
            response = httpx.get(url, timeout=5.0)
            if response.status_code == 200:
                print(f"✓ {url} is responding")
                return
        except (httpx.ConnectError, httpx.TimeoutException):
            pass

        time.sleep(1)

    raise TimeoutError(f"HTTP endpoint {url} did not respond within {timeout}s")


@pytest.fixture(scope="module")
def docker_services(request):
    """
    Start Docker Compose services for E2E tests using docker/.env.example

    Validates the actual deployment configuration that ships to production.
    Fails fast with clear errors if ports are already in use.

    Supports environment variable overrides via docker_services_env_override fixture.
    """
    # Check for port conflicts
    if port_in_use(settings.PGPORT):
        pytest.fail(
            f"❌ Port {settings.PGPORT} already in use!\n"
            "Stop the conflicting container: docker stop forgetful-db"
        )

    if port_in_use(settings.SERVER_PORT):
        pytest.fail(
            f"❌ Port {settings.SERVER_PORT} already in use!\n"
            "Stop the conflicting container: docker stop forgetful-service"
        )

    print("\n✓ Port availability check passed")

    # Setup variables for cleanup
    project_root = Path(__file__).parent.parent.parent
    compose_file = project_root / "docker" / "docker-compose.yml"
    env = os.environ.copy()
    env["ENVIRONMENT"] = "example"
    env["COMPOSE_PROJECT_NAME"] = "forgetful"  # Force lowercase project name

    # Check for environment variable overrides from test module
    override_file = None
    if hasattr(request, 'module') and hasattr(request.module, 'DOCKER_ENV_OVERRIDE'):
        env_override = request.module.DOCKER_ENV_OVERRIDE
        print(f"📝 Applying environment overrides: {env_override}")

        # Create a temporary docker-compose override file
        override_config = {
            'services': {
                'forgetful-service': {
                    'environment': [f"{key}={value}" for key, value in env_override.items()]
                }
            }
        }

        # Write override file
        fd, override_file = tempfile.mkstemp(suffix='.yml', prefix='docker-compose-override-')
        try:
            with os.fdopen(fd, 'w') as f:
                yaml.dump(override_config, f)
            print(f"📝 Created override file: {override_file}")
        except:
            os.close(fd)
            raise

    try:
        # Build docker compose command
        compose_cmd = ["docker", "compose", "-f", str(compose_file)]
        if override_file:
            compose_cmd.extend(["-f", override_file])
        compose_cmd.extend(["up", "-d"])

        # Start containers
        print("Starting Docker Compose services...")
        result = subprocess.run(
            compose_cmd,
            env=env,
            capture_output=True,
            text=True,
            cwd=str(project_root)
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Docker Compose failed to start:\n"
                f"STDOUT: {result.stdout}\n"
                f"STDERR: {result.stderr}"
            )

        # Wait for services to be healthy
        print("Waiting for services to be healthy...")
        wait_for_healthy("forgetful-db")
        wait_for_healthy("forgetful-service")

        # Wait for HTTP endpoint
        wait_for_http(f"http://localhost:{settings.SERVER_PORT}/health")

        print("✓ All services ready for testing\n")

        yield  # Tests run here

    finally:
        # Teardown - ALWAYS cleanup, even if tests or setup failed
        print("\nTearing down Docker Compose services...")
        compose_down_cmd = ["docker", "compose", "-f", str(compose_file)]
        if override_file:
            compose_down_cmd.extend(["-f", override_file])
        compose_down_cmd.extend(["down", "-v"])

        subprocess.run(
            compose_down_cmd,
            env=env,
            check=False,  # Don't fail if cleanup has issues
            cwd=str(project_root)
        )

        # Clean up temporary override file
        if override_file and os.path.exists(override_file):
            try:
                os.unlink(override_file)
                print(f"✓ Removed override file: {override_file}")
            except Exception as e:
                print(f"⚠ Failed to remove override file: {e}")

        print("✓ Cleanup complete")


@pytest.fixture
def server_base_url():
    """Returns the base URL of the running server for E2E tests"""
    return f"http://localhost:{settings.SERVER_PORT}"


@pytest.fixture
def mcp_server_url():
    """Returns the MCP protocol endpoint URL for E2E tests"""
    return f"http://localhost:{settings.SERVER_PORT}/mcp"
