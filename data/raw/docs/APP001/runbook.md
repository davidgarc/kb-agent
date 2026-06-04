# APP001 Checkout Runbook

## First Checks

Check checkout-api p95 latency, orders database active connections, and payment-worker queue lag. Confirm the queue name is `checkout-payment-events` and that the consumer group is `payment-worker-prod`.

## Database Triage

For orders database errors, inspect `orders-db-primary` connection count, slow query dashboard, and max pool settings. Escalate to Database Operations if active connections exceed 85 percent for more than ten minutes.

## Payment Callback Triage

For failed callbacks, compare AcmePay Gateway webhook delivery status with payment-worker retries. A mismatch between documented queue names and deployed queue bindings can leave old consumers processing stale events.
