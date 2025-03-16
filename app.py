def main():
    print("Hello, GitHub!")
    print("This is a sample application to demonstrate Git and GitHub workflow.")
    
    # Simple calculator functions
    num1 = 5
    num2 = 7
    
    # Addition
    add_result = add(num1, num2)
    print(f"The sum of {num1} and {num2} is {add_result}")
    
    # Multiplication
    mult_result = multiply(num1, num2)
    print(f"The product of {num1} and {num2} is {mult_result}")

def add(a, b):
    return a + b

def multiply(a, b):
    return a * b

if __name__ == "__main__":
    main()
