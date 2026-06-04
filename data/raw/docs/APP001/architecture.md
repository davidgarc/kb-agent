# APP001 Customer Checkout Architecture

## Overview

APP001 is the customer checkout and payment service for web and mobile purchases. It owns checkout session creation, payment authorization, order placement, and payment callback processing. The service is tier 1 because checkout availability directly affects revenue.

## Components

- `checkout-frontend` renders the customer checkout experience.
- `checkout-api` validates carts, calls inventory availability, creates orders, and starts payment authorization.
- `payment-worker` consumes payment callback events and updates order settlement state.
- `orders-db-primary` is the PostgreSQL primary used by checkout-api and payment-worker.

## Dependencies

APP001 depends on APP002 `inventory-api` for inventory reservation checks. It depends on the external `AcmePay Gateway` for payment authorization and callback delivery. Internal async payment work uses the `checkout-payment-events` queue.

## Known Failure Modes

Checkout latency commonly comes from orders database pool exhaustion, slow inventory reservation responses, payment gateway callback retries, or payment queue backlog. If payment-worker queue lag increases while checkout-api latency rises, inspect queue consumer bindings and database connection pressure together.

## Environments

Production runs in namespace `payments-prod` on cluster `use1-core-01`. The public ingress is `checkout.example.com`.
