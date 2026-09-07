# LedgerCore

LedgerCore is a backend financial wallet and ledger system built with **Django REST Framework**.

The project provides multi-currency wallets, financial transactions, cryptocurrency exchange, ledger tracking, caching, background tasks, real-time features, and API documentation.

## Tech Stack

* **Python 3.13**
* **Django 6**
* **Django REST Framework**
* **PostgreSQL**
* **Redis**
* **Celery**
* **Celery Beat**
* **Django Channels**
* **WebSocket**
* **Docker / Docker Compose**
* **JWT Authentication**
* **DRF Spectacular**
* **OpenAPI**
* **Swagger UI**
* **ReDoc**
* **Pytest**
* **pytest-django**
* **pytest-asyncio**
* **pytest-cov**

## Architecture

The project follows a service-oriented approach inside Django.

```text
                         Client
                        /      \
                       /        \
                    HTTP      WebSocket
                     │             │
                     ▼             ▼
                  DRF API     Django Channels
                     │             │
             Authentication        │
                     │             │
             Serializers /         │
               Validation          │
                     │             │
                     ▼             │
                   Views           │
                     │             │
                     ▼             │
                 Services          │
                     │             │
              ┌──────┴──────┐      │
              │             │      │
              ▼             ▼      │
         PostgreSQL       Redis ◄──┘
                            │
                    ┌───────┴────────┐
                    │                │
                  Cache        Channel Layer
```

Business-critical financial logic is kept inside **service functions** rather than views. Views are mainly responsible for authentication, validation, request handling, and returning API responses.

## Core Wallet

LedgerCore supports multiple currencies and provides independent wallets for supported currencies.

Implemented operations include:

* Deposit
* Withdraw
* Transfer
* Transaction history
* Ledger entries
* Multi-currency wallets

Financial operations use:

* `transaction.atomic()` for atomic operations
* `select_for_update()` for wallet locking
* `Decimal` for monetary calculations
* Idempotency keys to prevent duplicate operations

## Exchange

The exchange system allows users to exchange funds between their own wallets using stored exchange-rate snapshots.

The exchange flow is approximately:

```text
Exchange Request
      │
      ▼
Validate currencies & amount
      │
      ▼
Find source / destination wallets
      │
      ▼
Load latest exchange rate
      │
      ▼
Calculate exchange amount & fee
      │
      ▼
Lock wallets
      │
      ▼
Create Transaction
      │
      ├── ExchangeTransaction
      └── Ledger Entries
      │
      ▼
Update wallet balances
```

Exchange rates are obtained from an external exchange-rate API and stored as snapshots in the database.

Exchange transactions record:

* Source currency
* Destination currency
* Source amount
* Destination amount
* Exchange rate
* Fee
* Fee currency
* Transaction status
* Creation / completion timestamps

## Real-Time Features

LedgerCore uses **Django Channels** and **WebSockets** to provide real-time updates without requiring clients to continuously poll the API.

### Live Exchange Rates

Exchange-rate updates are broadcast to connected clients through a shared WebSocket group.

```text
Celery Beat
    │
    ▼
Exchange Rate Task
    │
    ▼
Save ExchangeRate
    │
    ▼
transaction.on_commit()
    │
    ▼
Channel Layer (Redis)
    │
    ▼
exchange_rates group
    │
    ▼
Connected WebSocket Clients
```

WebSocket endpoint:

```text
/ws/exchange-rates/
```

### User Notifications

Transaction-related notifications are delivered to authenticated users through private WebSocket groups.

Each user has a dedicated group:

```text
notifications_user_<user_id>
```

This allows multiple connections for the same user while preventing notifications from being delivered to other users.

Notifications are sent after a successful database transaction using `transaction.on_commit()`.

Supported transaction notifications include:

* Deposit
* Withdraw
* Transfer
* Exchange

WebSocket endpoint:

```text
/ws/notifications/
```

WebSocket connections use Django authentication through `AuthMiddlewareStack`.

## Redis & Caching

**Redis** is used for application caching and as the Channels channel layer.

Cached resources include:

* Wallet lists and wallet details
* Transaction history
* Exchange rates

Cache invalidation is performed when relevant financial data changes to prevent stale wallet or transaction information.

## Celery & Celery Beat

**Celery** handles background tasks that should not block API requests.

**Celery Beat** is used for scheduled tasks, including periodic exchange-rate updates.

```text
Celery Beat
    │
    ▼
Scheduled Task
    │
    ▼
External Exchange API
    │
    ▼
ExchangeRate Snapshot
    │
    ▼
Redis Cache
```

## API Documentation

The API is documented using **DRF Spectacular** and **OpenAPI**.

Available documentation interfaces:

* Swagger UI
* ReDoc
* OpenAPI schema

API endpoints include authentication, wallets, transactions, exchange rates, and currency exchange operations.

## Testing

The project uses **Pytest** with `pytest-django`, `pytest-asyncio`, and `pytest-cov`.

Tests cover the main business, API, background-task, and real-time flows, including:

* Wallet operations
* Deposits, withdrawals and transfers
* Transaction history
* Exchange service
* Exchange API
* Exchange rates
* Idempotency
* Insufficient balance
* Authentication and authorization
* Atomicity
* Ledger entries
* Background tasks
* WebSocket connections
* Real-time exchange-rate updates
* User notifications
* Notification user isolation
* Anonymous WebSocket access rejection

Current test suite:

**83 tests — 97% overall coverage**

The goal is to test important business behavior and prevent financial logic bugs rather than artificially maximizing code coverage.
