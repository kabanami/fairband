"""The valuation engine: pure computation on tagged inputs, no I/O.

Every route returns a ``fairband.engine.types.ValuationResult``; a refusal is a result with no
value and a reason, never an exception. ``METHOD_VERSION`` names the method each result cites.
"""

METHOD_VERSION = "fairband-mechanical/0.3"
