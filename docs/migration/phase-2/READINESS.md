# Phase 2A Computer Readiness

## Status

**Completed on 2026-08-27.**

Phase 2A checked and prepared the local computer for the FastAPI, PostgreSQL, and Keycloak development stack. It did not create containers, images, volumes, databases, backend code, cloud resources, or project secrets.

## System Results

| Check | Result | Status |
|---|---|---|
| Operating system | Microsoft Windows 11 Home, version `10.0.26200`, build `26200` | Ready |
| Architecture | AMD64, 64-bit Python verified | Ready |
| Virtualization | Windows reports `HypervisorPresent=True` | Ready |
| Physical memory | 15.86 GB total | Ready |
| Free memory after closing unnecessary applications | 5.98 GB | Ready; monitor while the stack runs |
| Free space on drive C after installation | 93.85 GB | Ready |
| Required ports | No listeners on `5432`, `8000`, or `8080` | Ready |

The first memory check showed only 0.69 GB free while other applications were open. Closing unnecessary applications restored 5.98 GB. PostgreSQL and Keycloak should not be started when Windows is already under strong memory pressure.

## Installed and Verified Tools

| Tool | Version or state | Notes |
|---|---|---|
| WSL | `2.7.12.0` | Installed during Phase 2A |
| WSL default | Version 2 | Verified with `wsl --status` |
| WSL kernel | `6.18.33.2-2` | Verified |
| Linux distribution | `docker-desktop`, running under WSL 2 | A separate Ubuntu distribution is not required |
| Docker Desktop | `4.88.1` | Installed and started successfully |
| Docker Engine client/server | `29.7.2` | Linux engine, non-experimental |
| Docker Compose | `5.4.0` | Verified in a fresh user terminal |
| Docker allocation | 12 CPUs and approximately 7.69 GiB maximum engine memory | No project containers or images exist yet |
| Python | `3.12.10` | Installed user-scoped alongside Anaconda Python 3.9 |
| pip for Python 3.12 | `25.0.1` | Verified |
| Existing Anaconda Python | `3.9.12` | Preserved and still selected by the plain `python` command |
| Node.js | `24.11.1` | Existing installation |
| npm | `11.6.2` | Existing installation |
| Git | `2.51.2.windows.1` | Existing installation |
| Windows Package Manager | `1.29.290` | Used for approved installations |

## Python Selection

The plain `python` command still resolves to Anaconda Python 3.9. This is intentional; Phase 2A did not modify Anaconda or force a global PATH change.

Use this interpreter to create the backend virtual environment in Phase 2B:

```text
C:\Users\aadhi\AppData\Local\Programs\Python\Python312\python.exe
```

After the virtual environment is active, backend commands will use its own `python` executable. This prevents the project from changing Anaconda packages.

## Docker State

Docker Desktop is using the `desktop-linux` context and WSL 2 Linux engine. At the end of Phase 2A it reported:

```text
Server version: 29.7.2
Operating system type: linux
CPUs available to engine: 12
Memory available to engine: 8,252,964,864 bytes
Containers: 0
Images: 0
```

The project has not pulled an image or created a container. Docker account login was completed by the project owner but is not required for the planned public base images.

## Changes Made to the Computer

- Enabled and updated WSL 2 without installing a separate general-purpose Linux distribution.
- Installed Python 3.12.10 for the current Windows user.
- Installed Docker Desktop 4.88.1.
- Started Docker Desktop and verified its Linux engine.
- Preserved Anaconda Python 3.9.12.
- Did not change project firewall rules manually.
- Did not enable Kubernetes.
- Did not create or disclose a password, access token, database connection string, or cloud credential.

## User Operating Instructions

- Start Docker Desktop before running the future local stack.
- Stop Docker Desktop when development is finished if memory or battery use matters.
- Close unnecessary memory-heavy applications before starting PostgreSQL and Keycloak.
- Keep at least 20 GB free; the current 93.85 GB is sufficient.
- Do not enable Kubernetes for this project.
- Do not manually create project containers through the Docker Desktop interface.
- Do not delete Docker volumes unless a later instruction explains the data impact and receives approval.
- Use the project commands that will be documented in later Phase 2 parts.

## Cost and Secrets

DigitalOcean cost: **USD 0**.

No project secret was created. Docker and Python installation introduced no Workloop database password, Keycloak administrator password, API key, or cloud token.

## Rollback

No rollback is required. The installed tools are prerequisites for the selected architecture and have not changed the current React or Supabase application.

If the migration is abandoned later, Docker Desktop and Python 3.12 can be removed through Windows Installed Apps. WSL must not be disabled without first checking whether another application uses it. Tool removal is a separate destructive system action and requires explicit approval.

## Completion Gate

Phase 2A passes because:

- Windows 11 and hardware virtualization support WSL 2.
- WSL 2 is installed and is the default.
- Docker Desktop, Docker Engine, and Docker Compose work.
- Python 3.12 and pip work without removing Anaconda.
- Node.js, npm, and Git work.
- Disk and free memory meet the development threshold after unnecessary applications are closed.
- Ports `5432`, `8000`, and `8080` are free.
- No project secret, container, volume, database, or cloud resource was created.

## Next Part

Phase 2B creates the backend scaffold and Python dependency configuration. It is on hold until the project owner explicitly authorizes it.
