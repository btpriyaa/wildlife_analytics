-- =============================================================
-- Wildlife Park Analytics — Snowflake Environment Setup
-- Run this as ACCOUNTADMIN once before first dbt run
-- =============================================================

USE ROLE ACCOUNTADMIN;

-- -----------------------------------------------
-- 1. DATABASES
-- -----------------------------------------------
CREATE DATABASE IF NOT EXISTS WILDLIFE_DEV  COMMENT = 'Development database for dbt models';
CREATE DATABASE IF NOT EXISTS WILDLIFE_PROD COMMENT = 'Production database for dbt models';

-- Raw schema to hold ingested source data (dev)
CREATE SCHEMA IF NOT EXISTS WILDLIFE_DEV.RAW;

-- -----------------------------------------------
-- 2. WAREHOUSES (separate dev vs prod to control costs)
-- -----------------------------------------------
CREATE WAREHOUSE IF NOT EXISTS DBT_DEV_WH
    WAREHOUSE_SIZE     = 'X-SMALL'
    AUTO_SUSPEND       = 60       -- suspend after 60s idle
    AUTO_RESUME        = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'dbt development warehouse — auto-suspends after 60s';

CREATE WAREHOUSE IF NOT EXISTS DBT_PROD_WH
    WAREHOUSE_SIZE     = 'SMALL'
    AUTO_SUSPEND       = 120
    AUTO_RESUME        = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'dbt production warehouse';

-- -----------------------------------------------
-- 3. ROLES
-- -----------------------------------------------
CREATE ROLE IF NOT EXISTS transformer COMMENT = 'Role used by dbt service account to run transformations';
CREATE ROLE IF NOT EXISTS reporter    COMMENT = 'Read-only role for analysts and BI tools';

-- Role hierarchy
GRANT ROLE transformer TO ROLE sysadmin;
GRANT ROLE reporter    TO ROLE sysadmin;

-- -----------------------------------------------
-- 4. WAREHOUSE ACCESS
-- -----------------------------------------------
GRANT USAGE ON WAREHOUSE DBT_DEV_WH  TO ROLE transformer;
GRANT USAGE ON WAREHOUSE DBT_PROD_WH TO ROLE transformer;

-- -----------------------------------------------
-- 5. DATABASE & SCHEMA ACCESS
-- -----------------------------------------------
-- transformer: full access to dev + prod
GRANT ALL PRIVILEGES ON DATABASE WILDLIFE_DEV  TO ROLE transformer;
GRANT ALL PRIVILEGES ON DATABASE WILDLIFE_PROD TO ROLE transformer;

GRANT ALL PRIVILEGES ON ALL SCHEMAS IN DATABASE WILDLIFE_DEV  TO ROLE transformer;
GRANT ALL PRIVILEGES ON ALL SCHEMAS IN DATABASE WILDLIFE_PROD TO ROLE transformer;

-- transformer: read raw source data
GRANT USAGE ON SCHEMA WILDLIFE_DEV.RAW TO ROLE transformer;
GRANT SELECT ON ALL TABLES IN SCHEMA WILDLIFE_DEV.RAW TO ROLE transformer;
GRANT SELECT ON FUTURE TABLES IN SCHEMA WILDLIFE_DEV.RAW TO ROLE transformer;

-- reporter: read-only on prod marts
GRANT USAGE ON DATABASE WILDLIFE_PROD TO ROLE reporter;
GRANT USAGE ON ALL SCHEMAS IN DATABASE WILDLIFE_PROD TO ROLE reporter;
GRANT SELECT ON ALL TABLES IN DATABASE WILDLIFE_PROD TO ROLE reporter;
GRANT SELECT ON FUTURE TABLES IN DATABASE WILDLIFE_PROD TO ROLE reporter;

-- -----------------------------------------------
-- 6. SERVICE ACCOUNT USER (dbt runner)
-- -----------------------------------------------
-- Replace <PASSWORD> with a secure password or use key-pair auth
CREATE USER IF NOT EXISTS dbt_service_account
    PASSWORD            = '<REPLACE_WITH_SECURE_PASSWORD>'
    DEFAULT_ROLE        = transformer
    DEFAULT_WAREHOUSE   = DBT_DEV_WH
    COMMENT             = 'Service account for dbt CI/CD pipeline';

GRANT ROLE transformer TO USER dbt_service_account;

-- -----------------------------------------------
-- 7. RESOURCE MONITORS (cost guardrails)
-- -----------------------------------------------
CREATE RESOURCE MONITOR IF NOT EXISTS dbt_dev_monitor
    WITH CREDIT_QUOTA = 20           -- Alert at 20 credits/month
    TRIGGERS
        ON 75 PERCENT DO NOTIFY      -- Email at 75%
        ON 100 PERCENT DO SUSPEND;   -- Suspend warehouse at 100%

ALTER WAREHOUSE DBT_DEV_WH SET RESOURCE_MONITOR = dbt_dev_monitor;

-- -----------------------------------------------
-- 8. VERIFY SETUP
-- -----------------------------------------------
SHOW WAREHOUSES LIKE 'DBT_%';
SHOW ROLES LIKE 'transformer';
SHOW ROLES LIKE 'reporter';
SHOW USERS LIKE 'dbt_service_account';
