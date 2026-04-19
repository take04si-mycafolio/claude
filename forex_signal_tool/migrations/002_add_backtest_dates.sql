-- Migration 002: Add start_date / end_date to backtest_results
-- Run once on the server:
--   mysql -u <user> -p <dbname> < migrations/002_add_backtest_dates.sql

ALTER TABLE backtest_results
  ADD COLUMN start_date DATETIME NULL AFTER profit_factor,
  ADD COLUMN end_date   DATETIME NULL AFTER start_date;
