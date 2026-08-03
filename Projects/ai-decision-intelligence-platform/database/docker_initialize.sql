:r schema/001_create_database.sql
GO
USE [AIDecisionIntelligence];
GO
:r schema/002_create_dimensions.sql
:r schema/003_create_facts.sql
:r schema/004_create_ai_tables.sql
:r schema/005_create_optimization_tables.sql
:r schema/006_create_views.sql
:r schema/007_create_indexes.sql
:r migrations/008_create_enterprise_operational_tables.sql
:r seeds/001_minimal_seed.sql
