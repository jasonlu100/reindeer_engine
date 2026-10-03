"""Allow ``python -m engine.packaging`` to invoke the packaging CLI."""
from engine.packaging.packager import main

if __name__ == "__main__":
    main()
