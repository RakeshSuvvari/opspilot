# INC-001: Missing DATABASE_URL

A deployment configuration regression removes `DATABASE_URL` from the payment container. The service fails during startup and Kubernetes restarts it until the pod enters `CrashLoopBackOff`.
