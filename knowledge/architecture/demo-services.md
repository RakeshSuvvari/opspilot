# OpsPilot demo service architecture

`checkout` depends on `inventory` over HTTP. `payment` is independent in Phase 1 and validates required database configuration during startup.

Healthy defaults:
- checkout inventory timeout: 500 ms
- inventory response delay: 100 ms
- payment requires `DATABASE_URL`
