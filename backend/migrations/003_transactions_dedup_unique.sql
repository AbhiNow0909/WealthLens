-- Makes CAS uploads idempotent: de-duplicate existing transactions, then add a
-- unique constraint so re-uploading the same statement can't create duplicates.
-- Run this in the Supabase SQL editor (Postgres 15+, which Supabase uses).

-- 1. Remove existing duplicate rows, keeping the earliest of each identical group.
delete from public.transactions t
using (
  select id,
         row_number() over (
           partition by user_id, isin, folio_number, transaction_date,
                        transaction_type, amount, units
           order by created_at
         ) as rn
  from public.transactions
) d
where t.id = d.id and d.rn > 1;

-- 2. Add the unique constraint. NULLS NOT DISTINCT treats null folio_number as
--    equal so those de-duplicate too (requires Postgres 15+).
alter table public.transactions
  add constraint transactions_unique_txn
  unique nulls not distinct (
    user_id, isin, folio_number, transaction_date, transaction_type, amount, units
  );
