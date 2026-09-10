# INC-006 - Missing Secret

payment reads DATABASE_URL from Secret payment-db, but the Secret is intentionally absent, producing CreateContainerConfigError.
