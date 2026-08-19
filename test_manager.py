from agents.manager import handle_request

print(handle_request("ask", "What is Python?"))

print(handle_request("remember", ("color", "blue")))

print(handle_request("recall", "color"))