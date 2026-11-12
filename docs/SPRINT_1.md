# Sprint 1: System Architecture & Scope Definition

## Section 1: Target Audience & Market Focus

- **Primary Persona:** Retail consumers aged 18–35 shopping for apparel and lifestyle accessories online, primarily via mobile.
- **Core Pain Point:** Small and mid-sized apparel sellers lack an affordable, easy-to-manage online storefront with reliable cart/checkout and inventory tracking, forcing them onto generic marketplaces with high commission and no brand control.
- **Domain Scope:** Apparel & Fashion Retail (clothing, footwear, accessories).

## Section 2: MVP Feature Scope Matrix

| Category | Feature Name | Description | Priority |
|---|---|---|---|
| Authentication | User Registration & Authentication | Password hashing (bcrypt) and JWT-based session/auth mechanism | High (MVP) |
| Catalog | Product List & Search | Browsing interface with category/size/color filtering | High (MVP) |
| Cart | Cart Management | Persistent cart (add, update quantity, remove) tied to user session | High (MVP) |
| Checkout | Order Processing | Stripe test-mode payment integration and order object creation | High (MVP) |
| Admin | Inventory Control | Admin CRUD for products, stock levels, and categories | Medium |
| Account | Order History | User-facing view of past orders and status | Medium |

## Section 3: Tech Stack Selection & Justification

- **Frontend Framework:** React (with Vite)
  *Justification:* Component-based structure suits a catalog/cart/checkout flow well, has the largest ecosystem for UI libraries, and integrates cleanly with a REST API backend.

- **Backend Infrastructure:** FastAPI (Python)
  *Justification:* Async support handles concurrent cart/checkout requests efficiently, built-in Pydantic validation reduces bugs around order/payment data, and auto-generated OpenAPI docs speed up frontend integration.

- **Database Management System:** PostgreSQL
  *Justification:* Orders, order items, and inventory need strict relational integrity (foreign keys, transactions) that a relational DB enforces natively; a document store like MongoDB would require manual consistency handling for stock counts during checkout.

- **Caching & Async Processing (Optional):** Redis + Celery
  *Justification:* Redis backs cart session persistence for guest users; Celery offloads order-confirmation emails so checkout requests return fast.

## Section 4: System Architecture Overview

```mermaid
flowchart TB
    subgraph Client["Client Layer"]
        A[React + Vite Web App]
    end

    subgraph API["Application Layer"]
        B[FastAPI REST API]
        C[JWT Auth Middleware]
        D[Celery Worker]
    end

    subgraph Data["Data Layer"]
        E[(PostgreSQL)]
        F[(Redis Cache)]
    end

    subgraph External["External Services"]
        G[Stripe Payment Gateway]
    end

    A -- HTTPS / REST --> B
    B --> C
    B -- Reads/Writes --> E
    B -- Session & Cart Cache --> F
    B -- Async Tasks --> D
    D -- Order Confirmation Email --> A
    B -- Checkout Request --> G
    G -- Payment Status --> B

    style Client fill:#e8f0fe,stroke:#4285f4
    style API fill:#fef7e0,stroke:#f9ab00
    style Data fill:#e6f4ea,stroke:#34a853
    style External fill:#fce8e6,stroke:#ea4335
```

## Section 5: Entity-Relationship Diagram (ERD)

```mermaid
erDiagram
    USERS ||--o{ ORDERS : places
    USERS ||--|| CART : owns
    ORDERS ||--|{ ORDER_ITEMS : contains
    PRODUCTS ||--o{ ORDER_ITEMS : ordered_in
    PRODUCTS ||--o{ CART_ITEMS : added_as
    CATEGORIES ||--o{ PRODUCTS : categorizes
    CART ||--|{ CART_ITEMS : contains

    USERS {
        int id PK
        string email
        string password_hash
        string full_name
        timestamp created_at
    }
    CATEGORIES {
        int id PK
        string name
        string slug
    }
    PRODUCTS {
        int id PK
        int category_id FK
        string name
        string description
        decimal price
        int stock_quantity
        string size
        string color
        timestamp created_at
    }
    ORDERS {
        int id PK
        int user_id FK
        decimal total_amount
        string status
        string payment_status
        timestamp created_at
    }
    ORDER_ITEMS {
        int id PK
        int order_id FK
        int product_id FK
        int quantity
        decimal unit_price
    }
    CART {
        int id PK
        int user_id FK
        timestamp updated_at
    }
    CART_ITEMS {
        int id PK
        int cart_id FK
        int product_id FK
        int quantity
    }
```

**Cardinality summary:**
- USERS 1:N ORDERS, 1:1 CART
- ORDERS 1:N ORDER_ITEMS (associative entity resolving ORDERS N:M PRODUCTS)
- CATEGORIES 1:N PRODUCTS
- CART 1:N CART_ITEMS (associative entity resolving CART N:M PRODUCTS)

## Section 6: Checkout Flow (Sequence)

```mermaid
sequenceDiagram
    participant U as User
    participant F as React Frontend
    participant B as FastAPI Backend
    participant D as PostgreSQL
    participant S as Stripe

    U->>F: Click "Checkout"
    F->>B: POST /orders (cart items)
    B->>D: Validate stock & create Order (status: pending)
    D-->>B: Order created
    B->>S: Create payment intent
    S-->>B: Payment confirmation
    B->>D: Update Order (status: paid)
    B-->>F: Order confirmation
    F-->>U: Show success page
```
