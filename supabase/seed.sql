-- LOCAL DEVELOPMENT ONLY. Runs after migrations on `supabase db reset`.
-- Reference data is loaded separately by `make refdata` from reference-data/ (cited sources).
alter role engine_app with password 'engine_app_local_only';
