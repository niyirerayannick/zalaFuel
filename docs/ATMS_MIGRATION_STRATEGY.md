# Afrilott Transport Management System (ATMS) Migration Strategy

## Objective
Migrate from the legacy AFLMS fleet-focused implementation to a modular ATMS operations platform with profitability-centric transport management.

## Principles
- Keep migration reversible and low-risk.
- Run old and new modules in parallel during transition.
- Preserve historical data integrity.
- Disable GPS tracking runtime paths from production routing.

## Target Modular Architecture
- `transport.core`
- `transport.vehicles`
- `transport.drivers`
- `transport.customers`
- `transport.routes`
- `transport.trips`
- `transport.fuel`
- `transport.maintenance`
- `transport.finance`
- `transport.analytics`
- `transport.reports`

## Phase Plan

### Phase 1: Foundation (Completed in this refactor)
- Introduce new ATMS modular apps and models.
- Add service layer for trip/fuel/finance/dashboard analytics.
- Add assignment safeguards and financial auto-calculation logic.
- Remove live tracking routes from main URL routing and ASGI websocket flow.

### Phase 2: Data Mapping and Backfill
Create dedicated migration scripts/commands to map legacy records:
- Legacy `clients.ClientProfile` -> `atms_customers.Customer`
- Legacy `vehicles.Vehicle` -> `atms_vehicles.Vehicle`
- Legacy `drivers.DriverProfile` -> `atms_drivers.Driver`
- Legacy `logistics.Route` -> `atms_routes.Route`
- Legacy orders + dispatch records -> `atms_trips.Trip`
- Legacy fuel logs -> `atms_fuel.FuelEntry`
- Legacy maintenance logs -> `atms_maintenance.MaintenanceRecord`
- Legacy payments/expenses -> `atms_finance.Payment` / `atms_finance.Expense`

Recommended implementation:
- Add management command `python manage.py migrate_to_atms --dry-run`.
- Include deterministic idempotent upsert logic by unique business keys.
- Log unresolved references to CSV for manual remediation.

### Phase 3: Parallel Run
- Keep legacy modules read-only.
- New records written to ATMS tables only.
- Validate dashboard totals against legacy monthly reporting for 1–2 periods.

### Phase 4: Cutover
- Point all operational UIs and APIs to ATMS modules.
- Remove legacy menu links and permissions.
- Archive legacy tracking tables and code.

### Phase 5: Cleanup
- Drop legacy tracking app and websocket dependencies.
- Remove stale templates and URLs.
- Freeze data contracts and publish ATMS API documentation.

## Validation Checklist
- Assignment blocked for expired/invalid vehicle/driver.
- No double assignment while trip is active.
- Trip distance/cost/profit metrics auto-update correctly.
- Fuel entry updates trip fuel totals.
- Executive dashboard monthly totals match finance rollups.

## Rollback Strategy
- Preserve backups before each migration step.
- Use feature flags to revert UI/API to legacy routes.
- Keep ATMS migration commands idempotent so reruns are safe.
