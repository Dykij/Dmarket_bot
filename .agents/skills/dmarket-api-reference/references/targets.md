# Targets (Buy Orders) API Reference

**Verified against live Swagger**: `https://docs.dmarket.com/v1/swagger.json` (DMarket trading API v2.0.0) on 2026-09-27.

## Endpoints

### Create Target
`POST /marketplace-api/v1/user-targets/create`

### Cancel Target (Delete)
`POST /marketplace-api/v1/user-targets/delete`
*Note: This is the correct endpoint to cancel an active target, not /close.*

### Get User Targets (Active)
`GET /marketplace-api/v1/user-targets`

### Get Closed Targets
`GET /marketplace-api/v1/user-targets/closed`
*Note: Returns a list of historical/closed targets, this is NOT an endpoint to cancel an order.*
