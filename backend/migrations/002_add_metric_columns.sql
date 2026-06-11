-- Adds Treynor and turnover ratio columns to the fund_metrics cache.
-- Run this in the Supabase SQL editor. expense_ratio already exists.
--
-- treynor_ratio is stored as a percentage (e.g. 8.95 means 8.95%), so it uses
-- a slightly wider precision than the unitless ratios.

alter table public.fund_metrics
  add column if not exists treynor_ratio  numeric(10,4),
  add column if not exists turnover_ratio numeric(8,4);
