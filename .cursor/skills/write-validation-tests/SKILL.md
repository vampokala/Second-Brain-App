---
name: write-validation-tests
description: Generate high-quality validation tests covering happy path, error paths, boundaries, and concurrency. Use when adding tests to new or changed code, when coverage is below 80%, or when the user asks to write tests, increase coverage, or improve test quality.
---

# Write Validation Tests

## When to invoke

- After implementing new code that lacks tests.
- When `diff-cover` reports < 80% line or < 70% branch on changed code.
- When the user asks "add tests", "increase coverage", "write tests for X".

## Coverage Targets (non-negotiable)

- Line coverage on new/changed code: **≥ 80%**
- Branch coverage on new/changed code: **≥ 70%**
- Per-file floor: **≥ 60%** line
- Iterate until met. Do not lower thresholds.

## Workflow

```
- [ ] Step 1: Identify code under test
- [ ] Step 2: Enumerate cases (happy/error/boundary/concurrent)
- [ ] Step 3: Write tests using AAA + the right framework
- [ ] Step 4: Run coverage and identify gaps
- [ ] Step 5: Add tests for uncovered branches
- [ ] Step 6: Verify thresholds met
```

### Step 1: Identify code under test

For each public function/method in the diff, plan the test set.

### Step 2: Enumerate cases

Use this table for each unit:

```markdown
| Case Type | Input | Expected | Why |
|-----------|-------|----------|-----|
| Happy     | valid order | order processed | core behavior |
| Error     | DB down | throws OrderProcessingError with context | resilience |
| Boundary  | empty items | returns total=0 | edge case |
| Boundary  | max items (1000) | succeeds in <500ms | scale |
| Concurrency | 2 refunds in parallel | second throws AlreadyRefunded | invariant |
```

Aim for: 1 happy + ≥ 1 error + ≥ 1 boundary, plus concurrency if state is mutable.

### Step 3: Write tests with AAA

```python
def test_refund_fails_when_order_already_refunded():
    # Arrange
    order = OrderFactory.refunded()
    service = RefundService(repo=InMemoryRepo([order]))

    # Act + Assert
    with pytest.raises(OrderAlreadyRefundedError) as exc:
        service.refund(order.id)
    assert order.id in str(exc.value)
```

```typescript
it("rejects refund when order already refunded", async () => {
  const order = OrderFactory.refunded();
  const service = new RefundService(new InMemoryRepo([order]));

  await expect(service.refund(order.id)).rejects.toThrow(OrderAlreadyRefundedError);
});
```

```java
@Test
@DisplayName("refund fails when order is already refunded")
void refund_givenAlreadyRefundedOrder_throwsConflict() {
    var order = OrderFactory.refunded();
    var service = new RefundService(new InMemoryRepo(List.of(order)));

    assertThatThrownBy(() -> service.refund(order.id()))
        .isInstanceOf(OrderAlreadyRefundedException.class)
        .hasMessageContaining(order.id().toString());
}
```

### Step 4: Run coverage

```bash
bash scripts/check-coverage.sh
```

The script reports per-file and changed-line coverage, and exits non-zero if below threshold.

### Step 5: Add tests for uncovered branches

Read the coverage report. For each uncovered line, ask: what input triggers this branch? Write a test that exercises it.

Common uncovered branches:
- Error handlers (raise the underlying error in a fake)
- Null/None branches (pass None explicitly)
- Edge boundaries (empty collection, max value)

### Step 6: Verify

Re-run `scripts/check-coverage.sh`. Only stop when:
- Line coverage on changed code ≥ 80%
- Branch coverage on changed code ≥ 70%
- No file below 60% line

## Anti-Patterns to Avoid

- Tests that mock the function they're testing.
- Tests that assert on log messages (brittle).
- One test per code line — test behavior, not implementation.
- `expect(true).toBe(true)`, `assert True`, `assertTrue(true)` placeholders.
- Removing tests to fix flakiness instead of fixing the root cause.

## Property-Based Testing

For pure functions (no side effects), add a property test:

```python
from hypothesis import given, strategies as st

@given(st.lists(st.integers()))
def test_sort_is_idempotent(xs):
    assert sorted(sorted(xs)) == sorted(xs)
```

```typescript
import fc from "fast-check";

test("sort is idempotent", () => {
  fc.assert(fc.property(fc.array(fc.integer()), (xs) => {
    expect([...xs].sort().sort()).toEqual([...xs].sort());
  }));
});
```
