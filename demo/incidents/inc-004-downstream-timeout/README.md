# INC-004: Downstream timeout

A checkout configuration regression reduces its inventory timeout to 50 ms while inventory takes about 180 ms. Checkout therefore returns 503 and logs a downstream deadline/timeout error.
