# echo_server.py
## Connection didn't close when terminal 2 was closed
### Cause
No exception handling to actually run conn.close() after exceptions
### Fix
Wrap the connection loop in a try/except
### How I found it
Manually closing and reopening terminal 2

# server.py
## No response after nc 127.0.0.1 5050 on terminal 2
### Cause
Forgot to construct a User object in main
### Fix
Construct a User object and invoke it in main
### How I found it
Inspecting my definition of main() after the blank response

## Unexpected User names passing/failing
### Cause
Incorrect conditional logic on handle_nick (regex only matched a single char and `not(len(args[0]) > 0) and len(args[0])` instead of `not(len(args[0]) > 0 and len(args[0]))`)
### Fix
Update logic
### How I found it
A sweeping inspection of conditional logic throughout the file

## Loud errors when closing terminal 2
### Cause
Exception handling too narrow
### Fix
Broaden the exception handling scope
### How I found it
Manual testing

## Concurrency issues
### Cause
No multithreading for individual or multiple users
### Fix
Give each user their own thread
### How I found it
Referencing the provided starter_server.py file and the helper document