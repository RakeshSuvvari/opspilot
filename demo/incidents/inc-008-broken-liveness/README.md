# INC-008 - Broken liveness probe

inventory serves on 8080 but the liveness probe targets 8081, causing kubelet restarts.
