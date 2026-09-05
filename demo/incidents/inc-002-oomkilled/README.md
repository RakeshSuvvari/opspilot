# INC-002: OOMKilled

The checkout process deliberately touches roughly 192 MiB while Kubernetes limits the container to 64 MiB. The expected termination reason is `OOMKilled` with exit code 137.
