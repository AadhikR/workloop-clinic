# Part 14A external facts

## Method

Codex checked public DigitalOcean documentation and used an existing signed-in browser session for
read-only account pages. It made no API token, key, resource, alert, project, application, database,
bucket, network, or billing change. GitHub access was read-only. Unknown facts remain explicit.

## Record

| ID | Status | Fact | Source and date |
| --- | --- | --- | --- |
| `EXT-001` | verified | `workloop-clinic-dev` exists with ID `634213f9-2e43-4aea-8f4e-22ddc3ecdac9` and has no resources. | Authenticated project page, 2026-09-27 |
| `EXT-002` | verified | The account has no App Platform application. | Authenticated App Platform page, 2026-09-27 |
| `EXT-003` | verified | `fra1-default` is the default FRA1 VPC. Its ID is `b8b6d17b-eae4-47de-b2b5-9d10baabdd2d`, its CIDR is `10.114.0.0/20`, and it has no resources, NAT gateway, peering, or partner attachment. | Authenticated VPC page, 2026-09-27 |
| `EXT-004` | verified | The account has no managed database cluster. | Authenticated Managed Databases page, 2026-09-27 |
| `EXT-005` | verified | The account has no Spaces bucket. | Authenticated Spaces page, 2026-09-27 |
| `EXT-006` | verified | The account has no resource alert. No application exists for App Platform deployment alerts. | Authenticated Monitoring page, 2026-09-27 |
| `EXT-007` | verified | A USD 20 monthly spend alert is active at 75 and 100 percent. September usage is USD 0.95, fully offset by credit, with USD 20 prepayment remaining. The billing page was last updated at 09:58 GMT+4. | Authenticated billing pages, 2026-09-27 |
| `EXT-008` | verified | Migration foundation run `36320345154` passed on `d2d6c10d99599c2911cf02743cc93fc2bb0129c3`. It listed classification, backend quality, frontend regression, and full-stack smoke. | Authenticated GitHub Actions run, 2026-09-27 |
| `EXT-009` | verified | Official availability pages list App Platform in Frankfurt and PostgreSQL shared CPU and Spaces in FRA1. | DigitalOcean regional and product availability pages, 2026-09-27 |
| `EXT-010` | verified | Current inputs are USD 10 for `apps-s-1vcpu-1gb-fixed`, USD 25 for `apps-s-1vcpu-2gb`, USD 5 for `apps-s-1vcpu-0.5gb`, USD 15.15 for PostgreSQL 1 GiB with 10 GiB, USD 5 for Spaces Standard, and no charge for the included static site. | Official DigitalOcean pricing pages, 2026-09-27 |
| `EXT-011` | unknown | The exact DigitalOcean GitHub App installation scope is not visible from the empty app inventory, and no authenticated CLI or token is available. 14G must verify repository-only access before apply. | 14A read-only discovery, 2026-09-27 |
| `EXT-012` | unknown | The repository does not name the solo operator, routine and emergency MFA account references, recovery custody, or recovery-test date. 14G must record them in the approved target manifest. | Repository and provider read-only discovery, 2026-09-27 |

## Price calculation

The fixed monthly estimate is USD 65.15 before tax and overages. It consists of a USD 10 API
service, USD 25 Keycloak service, two USD 5 workers, USD 15.15 PostgreSQL cluster, USD 5 Spaces
subscription, and the included static site. Migration and expiry jobs are billed only while they
run. Storage beyond 250 GiB and excess bandwidth are variable.

The existing USD 20 alert is useful as an early warning, but it is not a hard limit. Part 14G must
review the current prices again, record every variable-charge owner, and obtain approval for the
exact target before apply.

Official sources:

- <https://docs.digitalocean.com/products/app-platform/details/pricing/>
- <https://docs.digitalocean.com/products/databases/postgresql/details/pricing/>
- <https://docs.digitalocean.com/products/spaces/details/pricing/>
- <https://docs.digitalocean.com/platform/regional-availability/>
- <https://docs.digitalocean.com/products/databases/postgresql/details/availability/>
- <https://docs.digitalocean.com/products/spaces/details/availability/>
