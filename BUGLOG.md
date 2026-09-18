# echo_server.py
## Connection didn't close when terminal 2 was closed
### Cause
No exception handling to actually run conn.close() after exceptions
### Fix
Wrap the connection loop in a try/except
### How I found it
Manually closing and reopening terminal 2