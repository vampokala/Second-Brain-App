---
name: refactor-for-complexity
description: Reduce a function's cognitive complexity to <= 15 using guard clauses, extract method, polymorphism, and parameter objects. Use when SonarQube/CI reports cognitive complexity violations, when a function exceeds 60 lines, or when the user asks to refactor, simplify, or reduce complexity.
---

# Refactor for Complexity

## When to invoke

- A function's cognitive complexity is > 15.
- Function length > 60 lines.
- Nesting depth > 3.
- User asks to "simplify", "refactor", "reduce complexity".

## Refactoring Order

Apply these techniques in order. Stop when complexity drops below 15.

### 1. Guard Clauses (handles most cases)

Replace nested `if` with early returns.

```python
# BEFORE — cognitive complexity 10
def charge(user, order):
    if user is not None:
        if user.active:
            if order is not None:
                if order.items:
                    return process(user, order)
                else:
                    return None
            else:
                return None
        else:
            raise InactiveUserError()
    else:
        raise MissingUserError()

# AFTER — complexity 4
def charge(user, order):
    if user is None:
        raise MissingUserError()
    if not user.active:
        raise InactiveUserError()
    if order is None or not order.items:
        return None
    return process(user, order)
```

### 2. Extract Method

Pull a logical block into a named function.

```typescript
// BEFORE — one function does too much
function processOrder(order: Order): Result {
  // 20 lines of validation
  // 30 lines of pricing
  // 20 lines of payment
}

// AFTER
function processOrder(order: Order): Result {
  const validated = validateOrder(order);
  const priced = priceOrder(validated);
  return chargeOrder(priced);
}
```

Naming rule: the extracted method's name describes intent, not implementation.

### 3. Replace Conditional with Polymorphism

When a function branches on a type/enum to choose behavior, dispatch via a map or strategy.

```python
# BEFORE
def calc_fee(account_type, amount):
    if account_type == "premium":
        return amount * 0.01
    elif account_type == "standard":
        return amount * 0.02
    elif account_type == "trial":
        return 0
    else:
        raise UnknownAccountType(account_type)

# AFTER
FEE_RATES: dict[AccountType, float] = {
    AccountType.PREMIUM: 0.01,
    AccountType.STANDARD: 0.02,
    AccountType.TRIAL: 0.0,
}

def calc_fee(account_type: AccountType, amount: Decimal) -> Decimal:
    return amount * Decimal(FEE_RATES[account_type])
```

### 4. Introduce Parameter Object

When a function has > 5 parameters, group related ones.

```java
// BEFORE
public Quote price(String sku, int qty, String region, String currency,
                   boolean isMember, LocalDate date, Discount d) { ... }

// AFTER
public Quote price(PricingRequest req) { ... }

record PricingRequest(
    String sku, int qty, Region region, Currency currency,
    Membership membership, LocalDate date, Discount discount
) {}
```

### 5. Replace Loop with Pipeline

Long imperative loops obscure intent. Use stream/iterator APIs.

```python
# BEFORE
total = 0
for item in order.items:
    if not item.refunded:
        if item.price > 0:
            total += item.price * item.qty

# AFTER
total = sum(
    item.price * item.qty
    for item in order.items
    if not item.refunded and item.price > 0
)
```

## After Refactoring

1. **Re-run tests** — refactoring without tests is wishful thinking.
2. **Re-measure complexity** with the project's complexity tool (radon, eslint-plugin-sonarjs, sonar-scanner).
3. **Update or add tests for extracted methods** — newly-public functions deserve direct tests.
4. **Verify behavior unchanged** — compare outputs against the prior version if possible.

## When NOT to refactor

- Don't refactor without tests in place; add tests first.
- Don't refactor purely to satisfy a metric if it makes the code less clear. Request an exemption with justification instead.
- Don't refactor across unrelated boundaries in a single PR; split it.
