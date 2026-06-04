# APP002 Inventory Fulfillment Architecture

## Overview

APP002 provides inventory reservation and stock availability for checkout and fulfillment workflows. APP001 calls APP002 before payment authorization so customers do not purchase unavailable products.

## Components

- `inventory-api` exposes reservation and availability endpoints.
- `stock-cache` stores hot availability data.
- `inventory-db-primary` stores durable item and location stock state.

## Dependencies

APP002 depends on `inventory-db-primary` and `stock-cache`. APP001 depends on APP002 through the `inventory-api` REST endpoint.

## Known Failure Modes

Cache eviction and catalog refresh jobs can produce latency spikes that are visible to APP001 checkout-api as reservation delays.
