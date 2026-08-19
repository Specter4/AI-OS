from core.router import route_message
from agents.manager import handle_request

request = route_message("remember company = AI-OS")
print(handle_request(request))

request = route_message("recall company")
print(handle_request(request))

request = route_message("What is Python?")
print(handle_request(request))