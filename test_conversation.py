from core.conversation import (
    add_message,
    get_history,
    clear
)

clear()

add_message("user", "Hello")

add_message("assistant", "Hi!")

add_message("user", "I want to build a website.")

print(get_history())