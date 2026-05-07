def fibonacci(n):
    if n <= 0:
        return 0
    elif n == 1:
        return 1
    else:
        return fibonacci(n-1) + fibonacci(n-2)

# Print Fibonacci numbers up to 100
print("Fibonacci numbers up to 100:")
i = 0
while True:
    fib_num = fibonacci(i)
    if fib_num > 100:
        break
    print(f"F({i}) = {fib_num}")
    i += 1