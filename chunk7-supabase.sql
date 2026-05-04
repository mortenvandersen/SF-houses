-- Adds the two new status columns introduced in the redesign.
-- Run once against the project that backs sklvnnnxcgnkbccvvwpx.supabase.co.
-- The dashboard auto-detects whether the columns exist; once they do,
-- "Scheduled Tour" and "Applied" status selections become persistent.

alter table public.listing_flags
  add column if not exists scheduled_tour boolean not null default false,
  add column if not exists applied         boolean not null default false;
