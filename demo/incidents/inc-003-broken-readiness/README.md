# INC-003: Broken readiness probe

The inventory process listens on 8080 but its readiness probe is changed to 8081. The process keeps running while the pod remains unready and Kubernetes events record probe failures.
