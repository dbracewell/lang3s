"""Compatibility entrypoint for starting backend services.

This delegates to the maintained service runner in `lang3s.services.run`.
"""

from lang3s.services.run import main

if __name__ == "__main__":
    main()
