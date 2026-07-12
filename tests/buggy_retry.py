"""Buggy retry function — Example 4: Exception Handling

Bug: The retry decorator catches ALL exceptions including KeyboardInterrupt
     and SystemExit. It should only catch Exception subclasses and let
     critical exceptions propagate immediately.

Requirement: retry() should re-raise KeyboardInterrupt, SystemExit, and
             non-Exception BaseException subclasses without retrying.
"""


def retry(func, max_attempts=3):
    """Execute func with retries on failure.

    Bug: Catches BaseException (too broad), swallowing KeyboardInterrupt.
    Requirement: Only retry on Exception subclasses.
    """
    last_error = None
    for attempt in range(max_attempts):
        try:
            return func()
        except BaseException as e:  # Bug: too broad
            last_error = e
            continue
    raise last_error
